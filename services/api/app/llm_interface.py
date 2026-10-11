"""Provider-neutral contract for the HomePilot orchestrator's model calls."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, Sequence

MessageRole = Literal["system", "user", "assistant", "tool"]


@dataclass(frozen=True)
class FunctionCall:
    """A proposed tool call. The orchestrator must validate it before execution."""

    name: str
    arguments: dict[str, Any] = field(default_factory=dict)
    call_id: str | None = None


@dataclass(frozen=True)
class Message:
    """Provider-independent conversation turn for an agent loop."""

    role: MessageRole
    content: str = ""
    tool_calls: tuple[FunctionCall, ...] = ()
    tool_name: str | None = None
    tool_call_id: str | None = None
    provider_content: tuple[dict[str, Any], ...] | None = None


@dataclass(frozen=True)
class FunctionDefinition:
    """A JSON-schema function the model may propose calling."""

    name: str
    description: str
    parameters: dict[str, Any]


@dataclass(frozen=True)
class LLMResponse:
    content: str
    function_calls: tuple[FunctionCall, ...] = ()
    finish_reason: str | None = None
    model: str | None = None
    provider_content: tuple[dict[str, Any], ...] | None = None


class LLMProvider(Protocol):
    """Interface implemented by model providers consumed by the orchestrator."""

    async def complete(
        self,
        messages: Sequence[Message],
        *,
        functions: Sequence[FunctionDefinition] = (),
        temperature: float | None = None,
    ) -> LLMResponse:
        """Return assistant text and/or proposed function calls for this turn."""
        ...
