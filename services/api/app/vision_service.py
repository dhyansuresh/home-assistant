"""VLM provider backed by HomePilot's internal vision service (``/internal/recognize``)."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any

import httpx

from app.settings import load_local_environment
from app.vlm_interface import VLMError, VLMRequest, VLMResponse

MAX_CANDIDATES = 5
MAX_FIELD_LENGTH = 120
CONTROL_CHARACTERS = re.compile(r"[\x00-\x1f\x7f]+")


@dataclass(frozen=True)
class RecognitionResponse(VLMResponse):
    """A ``VLMResponse`` that also keeps the validated ``RecognitionResult`` for later loop stages."""

    recognition: dict[str, Any] | None = None


class VisionServiceProvider:
    """Send the request's image to the dedicated vision model and describe its structured result.

    The description is untrusted evidence for the LLM. It preserves the model's ranking and the
    unknown outcome; it never upgrades an unknown result to a product identification.
    """

    def __init__(
        self,
        base_url: str | None = None,
        *,
        timeout_seconds: float = 10.0,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        load_local_environment()
        self._base_url = (base_url or os.getenv("VISION_SERVICE_URL", "http://localhost:8001")).rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._http_client = http_client

    async def describe(self, request: VLMRequest) -> RecognitionResponse:
        owns_client = self._http_client is None
        client = self._http_client or httpx.AsyncClient(timeout=self._timeout_seconds)
        try:
            response = await client.post(
                f"{self._base_url}/internal/recognize",
                files={"image": ("upload", request.image, request.content_type)},
                timeout=self._timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise VLMError("Vision service request failed") from exc
        finally:
            if owns_client:
                await client.aclose()
        recognition = validate_recognition(payload)
        return RecognitionResponse(description=summarize(recognition), recognition=recognition)


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise VLMError("Vision service returned a non-text product field")
    text = CONTROL_CHARACTERS.sub(" ", value).strip()[:MAX_FIELD_LENGTH]
    return text or None


def validate_recognition(payload: Any) -> dict[str, Any]:
    """Check the ``RecognitionResult`` contract; malformed output is an operational error."""
    required = {"recognition_id", "model_id", "unknown", "requires_confirmation", "candidates"}
    if not isinstance(payload, dict) or set(payload) != required:
        raise VLMError("Vision service returned unexpected fields")
    if type(payload["unknown"]) is not bool or payload["requires_confirmation"] is not True:
        raise VLMError("Vision service returned an invalid recognition status")
    if not isinstance(payload["model_id"], str) or not isinstance(payload["recognition_id"], str):
        raise VLMError("Vision service returned invalid identifiers")
    candidates = payload["candidates"]
    if not isinstance(candidates, list) or (payload["unknown"] and candidates):
        raise VLMError("Vision service returned invalid candidates")
    if not payload["unknown"] and not candidates:
        raise VLMError("A known recognition needs at least one candidate")
    cleaned = []
    for expected_rank, candidate in enumerate(candidates[:MAX_CANDIDATES], start=1):
        if not isinstance(candidate, dict) or not {"name", "rank", "score"} <= set(candidate) \
                or not set(candidate) <= {"name", "brand", "size_label", "rank", "score"}:
            raise VLMError("Vision service returned an invalid candidate")
        score = candidate["score"]
        if candidate["rank"] != expected_rank or (score is not None and not isinstance(score, (int, float))):
            raise VLMError("Vision service returned invalid candidate ranking")
        name = _clean(candidate["name"])
        if not name:
            raise VLMError("Vision service returned a candidate without a name")
        cleaned.append({"name": name, "brand": _clean(candidate.get("brand")),
                        "size_label": _clean(candidate.get("size_label")),
                        "rank": expected_rank, "score": score})
    return {**payload, "model_id": _clean(payload["model_id"]) or "unknown-model", "candidates": cleaned}


def summarize(recognition: dict[str, Any]) -> str:
    """Plain-text evidence for the LLM context; keeps ranking, raw scores and unknown status."""
    source = f"Dedicated product-recognition model ({recognition['model_id']})"
    if recognition["unknown"]:
        return (f"{source}: unknown. An object was submitted, but it did not confidently match any product "
                "in the registered catalog. Do not guess the product; ask the user to identify it.")
    lines = [f"{source} ranked candidates (raw similarity scores, not confidence; the user must confirm):"]
    for candidate in recognition["candidates"]:
        label = " ".join(part for part in (candidate["brand"], candidate["name"], candidate["size_label"]) if part)
        score = "n/a" if candidate["score"] is None else f"{candidate['score']:.3f}"
        lines.append(f"{candidate['rank']}. {label} (score {score})")
    return "\n".join(lines)
