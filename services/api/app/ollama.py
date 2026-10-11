"""Ollama implementation of the provider-neutral orchestrator interface (local models, e.g. qwen3)."""

from __future__ import annotations

import json
import os
from typing import Any, Sequence
from urllib.parse import urlparse

import httpx

from app.llm_interface import FunctionCall, FunctionDefinition, LLMResponse, Message
from app.settings import load_local_environment

DEFAULT_BASE_URL = "http://127.0.0.1:11434"
DEFAULT_MODEL = "qwen3:8b"


class OllamaError(RuntimeError):
    """Raised when the local Ollama server is unavailable or returns an invalid response."""


class OllamaProvider:
    """Translate common orchestrator messages to Ollama's ``/api/chat`` API.

    Thinking is disabled so qwen3 answers directly; each command makes up to three calls.
    """

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        *,
        timeout_seconds: float = 120.0,
        keep_alive: str = "30m",
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        load_local_environment()
        self._base_url = (base_url or os.getenv("OLLAMA_BASE_URL", DEFAULT_BASE_URL)).rstrip("/")
        if urlparse(self._base_url).scheme not in ("http", "https"):
            raise ValueError("OLLAMA_BASE_URL must be an http(s) URL")
        self._model = (model or os.getenv("OLLAMA_MODEL", DEFAULT_MODEL)).strip()
        if not self._model:
            raise ValueError("OLLAMA_MODEL must not be blank")
        self._timeout_seconds = timeout_seconds
        self._keep_alive = keep_alive
        self._http_client = http_client

    async def complete(
        self,
        messages: Sequence[Message],
        *,
        functions: Sequence[FunctionDefinition] = (),
        temperature: float | None = None,
    ) -> LLMResponse:
        """Generate one turn using the shared ``LLMProvider`` contract.

        Returned function calls are proposals. Application code retains tool
        allowlisting, argument validation, confirmation, and execution control.
        """
        if not messages:
            raise ValueError("messages must include at least one conversation turn")

        body: dict[str, Any] = {
            "model": self._model,
            "messages": self._convert_messages(messages),
            "stream": False,
            "think": False,
            "keep_alive": self._keep_alive,
        }
        if functions:
            body["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": fn.name,
                        "description": fn.description,
                        "parameters": fn.parameters,
                    },
                }
                for fn in functions
            ]
        if temperature is not None:
            body["options"] = {"temperature": temperature}

        owns_client = self._http_client is None
        client = self._http_client or httpx.AsyncClient(timeout=self._timeout_seconds)
        try:
            response = await client.post(
                f"{self._base_url}/api/chat", json=body, timeout=self._timeout_seconds
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise OllamaError("Ollama request failed") from exc
        finally:
            if owns_client:
                await client.aclose()

        try:
            message = payload["message"]
            text = message.get("content") or ""
            if not isinstance(text, str):
                raise ValueError("invalid content")
            calls = []
            for raw in message.get("tool_calls") or []:
                function = raw["function"]
                arguments = function.get("arguments") or {}
                if isinstance(arguments, str):
                    arguments = json.loads(arguments)
                calls.append(FunctionCall(name=function["name"], arguments=arguments, call_id=raw.get("id")))
            if any(not call.name or not isinstance(call.arguments, dict) for call in calls):
                raise ValueError("invalid function call")
            return LLMResponse(
                content=text.strip(),
                function_calls=tuple(calls),
                finish_reason=payload.get("done_reason"),
                model=payload.get("model") or self._model,
            )
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            raise OllamaError("Ollama returned an invalid or empty response") from exc

    @staticmethod
    def _convert_messages(messages: Sequence[Message]) -> list[dict[str, Any]]:
        conversation: list[dict[str, Any]] = []
        for message in messages:
            if message.role == "tool":
                if not message.tool_name:
                    raise ValueError("tool messages require tool_name")
                conversation.append({"role": "tool", "tool_name": message.tool_name, "content": message.content})
                continue
            turn: dict[str, Any] = {"role": message.role, "content": message.content}
            if message.tool_calls:
                turn["tool_calls"] = [
                    {"function": {"name": call.name, "arguments": call.arguments}}
                    for call in message.tool_calls
                ]
            conversation.append(turn)
        return conversation
