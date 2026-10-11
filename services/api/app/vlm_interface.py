"""Types for the image-recognition step the orchestrator runs before asking the LLM."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class VLMError(RuntimeError):
    """The image could not be analysed (service down, timeout, or an invalid reply)."""


@dataclass(frozen=True)
class VLMRequest:
    image: bytes
    content_type: str


@dataclass(frozen=True)
class VLMResponse:
    """Plain-text evidence about the image for the LLM; ``None`` when there is nothing usable."""

    description: str | None


class VLMProvider(Protocol):
    async def describe(self, request: VLMRequest) -> VLMResponse:
        """Analyse one image. Must not change any application data."""
        ...
