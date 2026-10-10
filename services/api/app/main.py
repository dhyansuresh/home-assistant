"""FastAPI starter: health is real; integration routes are intentionally unfinished."""

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.settings import load_local_environment

load_local_environment()

app = FastAPI(title="HomePilot MVP API", version="0.1.0")


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
