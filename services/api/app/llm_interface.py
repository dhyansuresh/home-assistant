"""Types shared by the orchestrator and every language-model backend.

Backends translate these to and from their own wire format, so the orchestrator never
depends on one vendor's request shape.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, Sequence

Role = Literal["system", "user", "assistant", "tool"]


@dataclass(frozen=True)
class FunctionDefinition:
    """A tool the model may request, with its arguments described as a JSON Schema object."""

    name: str
    description: str
    parameters: dict[str, Any]


@dataclass(frozen=True)
class FunctionCall:
    """A tool request produced by the model. It is a proposal until backend code validates it."""

    name: str
    arguments: dict[str, Any] = field(default_factory=dict)
    call_id: str | None = None


@dataclass(frozen=True)
class Message:
    """One conversation turn.

    Assistant turns may carry the tool calls they made; a ``tool`` turn carries one tool's
    result and names that tool in ``tool_name``.
    """

    role: Role
    content: str = ""
    tool_calls: tuple[FunctionCall, ...] = ()
    tool_name: str | None = None
    tool_call_id: str | None = None


@dataclass(frozen=True)
class LLMResponse:
    """Text and/or tool requests returned by one model turn."""

    content: str
    function_calls: tuple[FunctionCall, ...] = ()
    finish_reason: str | None = None
    model: str | None = None


class LLMProvider(Protocol):
    async def complete(
        self,
        messages: Sequence[Message],
        *,
        functions: Sequence[FunctionDefinition] = (),
        temperature: float | None = None,
    ) -> LLMResponse:
        """Run one model turn over ``messages``, optionally offering ``functions``."""
        ...
