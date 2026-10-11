"""FastAPI application and orchestrator routes."""

from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.database import ShoppingListDatabase
from app.gemini import GeminiProvider
from app.orchestrator import InvalidCommandInput, Orchestrator
from app.runtime_mcp_client import RuntimeMCPGroceryListClient
from app.settings import load_local_environment
from app.vision_service import VisionServiceProvider
from app.vlm_interface import VLMError, VLMInputError, VLMRequest

MAX_ORCHESTRATOR_IMAGE_BYTES = 10 * 1024 * 1024

load_local_environment()

shopping_list_database = ShoppingListDatabase()
runtime_mcp_client = RuntimeMCPGroceryListClient(shopping_list_database.path)


@asynccontextmanager
async def lifespan(app: FastAPI):
    shopping_list_database.initialize()
    app.state.shopping_list_database = shopping_list_database
    yield


app = FastAPI(title="HomePilot MVP API", version="0.1.0", lifespan=lifespan)
orchestrator = Orchestrator(
    GeminiProvider(),
    vlm_provider=VisionServiceProvider(),
    grocery_list_store=runtime_mcp_client,
)


class OrchestratorRunResult(BaseModel):
    status: Literal["rejected", "in_progress", "completed"]
    valid: bool
    reason: str | None
    response: str | None = None


def unfinished() -> JSONResponse:
    return JSONResponse(
        status_code=501,
        content={"error": {"code": "not_implemented", "message": "Integration not implemented yet."}},
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/v1/recognitions")
def create_recognition() -> JSONResponse:
    return unfinished()


@app.get("/api/v1/inventory")
def get_inventory() -> JSONResponse:
    return unfinished()


@app.post("/api/v1/inventory/items")
def add_inventory_item() -> JSONResponse:
    return unfinished()


@app.patch("/api/v1/inventory/items/{item_id}")
def set_inventory_quantity(item_id: str) -> JSONResponse:
    return unfinished()


@app.get("/api/v1/grocery-list")
def get_grocery_list() -> JSONResponse:
    return unfinished()


@app.post("/api/v1/grocery-list/items")
def add_grocery_list_item() -> JSONResponse:
    return unfinished()


@app.post("/api/v1/agent/chat")
def agent_chat() -> JSONResponse:
    return unfinished()


@app.post("/api/v1/orchestrator/run", response_model=OrchestratorRunResult)
async def run_orchestrator(
    prompt: str = Form(...),
    image: UploadFile | None = File(default=None),
):
    vlm_request = None
    if image is not None:
        content_type = image.content_type or ""
        if not content_type.startswith("image/"):
            return JSONResponse(
                status_code=400,
                content={"error": {"code": "invalid_input", "message": "image must be an image file"}},
            )
        image_bytes = await image.read(MAX_ORCHESTRATOR_IMAGE_BYTES + 1)
        if len(image_bytes) > MAX_ORCHESTRATOR_IMAGE_BYTES:
            return JSONResponse(
                status_code=413,
                content={"error": {"code": "too_large", "message": "image exceeds 10 MiB"}},
            )
        if not image_bytes:
            return JSONResponse(
                status_code=400,
                content={"error": {"code": "invalid_input", "message": "image must not be empty"}},
            )
        vlm_request = VLMRequest(image=image_bytes, content_type=content_type)

    try:
        result = await orchestrator.run(
            prompt,
            image=vlm_request,
        )
    except InvalidCommandInput as exc:
        return JSONResponse(
            status_code=400,
            content={"error": {"code": "invalid_input", "message": str(exc)}},
        )
    except VLMInputError as exc:
        code = "too_large" if exc.status_code == 413 else "invalid_input"
        message = "image exceeds 10 MiB" if exc.status_code == 413 else "image could not be decoded"
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": code, "message": message}},
        )
    except VLMError:
        return JSONResponse(
            status_code=503,
            content={"error": {"code": "vision_unavailable", "message": "Image understanding is unavailable."}},
        )
    except Exception:
        return JSONResponse(
            status_code=503,
            content={
                "error": {
                    "code": "llm_unavailable",
                    "message": "The orchestrator could not complete the request.",
                }
            },
        )

    return OrchestratorRunResult(
        status=result.status,
        valid=result.valid,
        reason=result.reason,
        response=result.response,
    )
