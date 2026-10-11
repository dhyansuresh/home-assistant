"""Internal HomePilot vision service: one image in, ranked gallery candidates or unknown out.

Configuration (environment):
  VISION_GALLERY            gallery folder from register_gallery.py (required for /internal/recognize)
  VISION_MODEL              checkpoint used to build that gallery (default google/siglip2-base-patch16-224)
  VISION_UNKNOWN_THRESHOLD  override the gallery's suggested threshold (raw cosine, not a probability)
  VISION_DEVICE             cuda / mps / cpu (default: AMD ROCm GPU if present)
  VISION_TOP_K              candidates returned (default 3)
Called by FastAPI only; never expose this port publicly. Images are not stored or logged.
"""
import io
import logging
import os
import threading
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, UploadFile
from fastapi.responses import JSONResponse
from PIL import UnidentifiedImageError

from app.recognizer import Recognizer, open_rgb

MAX_IMAGE_BYTES = 10 * 1024 * 1024
log = logging.getLogger("homepilot.vision")
state: dict = {"recognizer": None, "error": None}
inference_lock = threading.Lock()  # one in-flight inference per process


def error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}})


@asynccontextmanager
async def lifespan(_app: FastAPI):
    gallery = os.getenv("VISION_GALLERY")
    if not gallery:
        state["error"] = "VISION_GALLERY is not configured"
    else:
        try:
            threshold = os.getenv("VISION_UNKNOWN_THRESHOLD")
            state["recognizer"] = Recognizer(
                os.getenv("VISION_MODEL", "google/siglip2-base-patch16-224"), gallery,
                device=os.getenv("VISION_DEVICE") or None,
                unknown_threshold=float(threshold) if threshold else None,
                top_k=int(os.getenv("VISION_TOP_K", "3")))
            r = state["recognizer"]
            log.warning("Vision ready: %s on %s, %d products, unknown threshold %.3f",
                        r.model_id, r.encoder.device, len(r.gallery.products), r.threshold)
        except Exception as exc:  # keep /health up so the failure is visible
            state["error"] = f"{type(exc).__name__}: {exc}"
            log.exception("Vision model failed to load")
    yield


app = FastAPI(title="HomePilot Vision", version="0.2.0", lifespan=lifespan)


@app.get("/health")
def health() -> dict:
    r = state["recognizer"]
    if r is None:
        return {"status": "degraded", "ready": False, "error": state["error"]}
    return {"status": "ok", "ready": True, "model_id": r.model_id, "device": r.encoder.device,
            "products": len(r.gallery.products), "unknown_threshold": r.threshold}


@app.post("/internal/recognize")
def recognize(image: UploadFile = File(...)):
    r = state["recognizer"]
    if r is None:
        return error(503, "vision_unavailable", state["error"] or "Vision model is not loaded")
    if not (image.content_type or "").startswith("image/"):
        return error(400, "invalid_input", "image must be an image file")
    data = image.file.read(MAX_IMAGE_BYTES + 1)
    if len(data) > MAX_IMAGE_BYTES:
        return error(413, "too_large", "image exceeds 10 MiB")
    if not data:
        return error(400, "invalid_input", "image must not be empty")
    try:
        photo = open_rgb(io.BytesIO(data))
    except (UnidentifiedImageError, OSError, ValueError):
        return error(400, "invalid_input", "image could not be decoded")
    started = time.perf_counter()
    with inference_lock:
        result = r.recognize(photo)
    recognition_id = str(uuid.uuid4())
    log.info("recognition %s unknown=%s best=%.3f %.0fms", recognition_id, result["unknown"],
             result["best_similarity"], (time.perf_counter() - started) * 1000)
    return {"recognition_id": recognition_id, "model_id": r.model_id, "unknown": result["unknown"],
            "requires_confirmation": True, "candidates": result["candidates"]}
