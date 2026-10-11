"""Provider-neutral request and response boundary for image description."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class VLMRequest:
    """Image bytes and media type passed to a vision-language model."""

    image: bytes
    content_type: str


@dataclass(frozen=True)
class VLMResponse:
    """Description returned for an image; empty means no usable description."""

    description: str | None


class VLMProvider(Protocol):
    """Interface the orchestrator uses to request an image description."""

    async def describe(self, request: VLMRequest) -> VLMResponse:
        """Describe the supplied image without performing application actions."""
        ...


class VLMError(RuntimeError):
    """Raised when the VLM cannot process or describe an image."""
