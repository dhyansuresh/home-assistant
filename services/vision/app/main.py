"""Vision API shape only. Model loading and ROCm dependencies belong to Developer 1."""

from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI(title="HomePilot Vision", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/internal/recognize")
def recognize() -> JSONResponse:
    return JSONResponse(
        status_code=501,
        content={"error": {"code": "not_implemented", "message": "Model inference not implemented yet."}},
    )
