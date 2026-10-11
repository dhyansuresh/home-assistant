"""HomePilot FastAPI app: the orchestrator route, task sessions, and contract placeholders."""

import os
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.database import GroceryListRepository
from app.llm_interface import LLMProvider
from app.ollama import OllamaProvider
from app.orchestrator import InvalidCommandInput, Orchestrator
from app.runtime_mcp_client import MCPGroceryList
from app.schemas import TaskSession, TaskSessionCreate
from app.settings import load_local_environment
from app.task_sessions import TaskSessionStore
from app.vision_service import VisionServiceProvider
from app.vlm_interface import VLMError, VLMRequest

MAX_IMAGE_BYTES = 10 * 1024 * 1024

load_local_environment()


def create_llm_provider() -> LLMProvider:
    """Return the orchestrator LLM: local Ollama (the only supported ``LLM_PROVIDER``)."""
    if os.getenv("LLM_PROVIDER", "ollama").strip().lower() != "ollama":
        raise ValueError("LLM_PROVIDER must be 'ollama'")
    return OllamaProvider()


grocery_list_repository = GroceryListRepository()
orchestrator = Orchestrator(
    create_llm_provider(),
    VisionServiceProvider(),
    grocery_list_store=MCPGroceryList(grocery_list_repository.path),
)
task_session_store = TaskSessionStore()


@asynccontextmanager
async def lifespan(_: FastAPI):
    grocery_list_repository.create_schema()
    yield


app = FastAPI(title="HomePilot MVP API", version="0.1.0", lifespan=lifespan)


class OrchestratorRunResult(BaseModel):
    status: Literal["rejected", "in_progress", "completed"]
    valid: bool
    reason: str | None
    response: str | None = None


def error(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"error": {"code": code, "message": message}})


def not_implemented() -> JSONResponse:
    return error(501, "not_implemented", "Integration not implemented yet.")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/v1/task-sessions", response_model=TaskSession, status_code=201)
def create_task_session(session_request: TaskSessionCreate) -> TaskSession:
    """Create and store a task session."""
    return task_session_store.create(session_request.mode)


# Routes defined in contracts/openapi.yaml that are not built yet. They answer 501 instead of
# pretending to work; grocery-list reads and additions currently go through the orchestrator.
for method, path in (
    ("POST", "/api/v1/recognitions"),
    ("GET", "/api/v1/inventory"),
    ("POST", "/api/v1/inventory/items"),
    ("PATCH", "/api/v1/inventory/items/{item_id}"),
    ("GET", "/api/v1/grocery-list"),
    ("POST", "/api/v1/grocery-list/items"),
    ("POST", "/api/v1/agent/chat"),
):
    app.add_api_route(path, not_implemented, methods=[method])


@app.post("/api/v1/orchestrator/run", response_model=OrchestratorRunResult)
async def run_orchestrator(prompt: str = Form(...), image: UploadFile | None = File(default=None)):
    photo = None
    if image is not None:
        if not (image.content_type or "").startswith("image/"):
            return error(400, "invalid_input", "image must be an image file")
        data = await image.read(MAX_IMAGE_BYTES + 1)
        if len(data) > MAX_IMAGE_BYTES:
            return error(413, "too_large", "image exceeds 10 MiB")
        if not data:
            return error(400, "invalid_input", "image must not be empty")
        photo = VLMRequest(image=data, content_type=image.content_type)

    try:
        result = await orchestrator.run(prompt, image=photo)
    except InvalidCommandInput as problem:
        return error(400, "invalid_input", str(problem))
    except VLMError:
        return error(503, "vision_unavailable", "Image understanding is unavailable.")
    except Exception:
        return error(503, "llm_unavailable", "The orchestrator could not complete the request.")
    return OrchestratorRunResult(status=result.status, valid=result.valid, reason=result.reason,
                                 response=result.response)
