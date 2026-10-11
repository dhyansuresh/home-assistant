"""Ollama chat API implementation of the shared LLM provider interface."""

from __future__ import annotations

import os
from typing import Any, Sequence
from urllib.parse import urlsplit

import httpx

from app.llm_interface import FunctionCall, FunctionDefinition, LLMResponse, Message
from app.settings import load_local_environment

DEFAULT_BASE_URL = "http://127.0.0.1:11434"
DEFAULT_MODEL = "qwen3"


class OllamaError(RuntimeError):
    """Raised when Ollama is unavailable or returns an unusable response."""


class OllamaProvider:
    """Translate orchestrator messages and function calls to Ollama's chat API."""

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        *,
        timeout_seconds: float = 180.0,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        load_local_environment()
        configured_url = base_url if base_url is not None else os.getenv(
            "OLLAMA_BASE_URL", DEFAULT_BASE_URL
        )
        configured_model = model if model is not None else os.getenv("OLLAMA_MODEL", DEFAULT_MODEL)
        parsed_url = urlsplit(configured_url)
        if (
            parsed_url.scheme not in ("http", "https")
            or not parsed_url.hostname
            or parsed_url.path not in ("", "/")
            or parsed_url.query
            or parsed_url.fragment
        ):
            raise ValueError("OLLAMA_BASE_URL must be an HTTP(S) server origin")
        if not configured_model.strip():
            raise ValueError("OLLAMA_MODEL must not be blank")
        self._base_url = configured_url.rstrip("/")
        self._model = configured_model.strip()
        self._timeout_seconds = timeout_seconds
        self._http_client = http_client

    async def complete(
        self,
        messages: Sequence[Message],
        *,
        functions: Sequence[FunctionDefinition] = (),
        temperature: float | None = None,
    ) -> LLMResponse:
        if not messages:
            raise ValueError("messages must include at least one conversation turn")

        body: dict[str, Any] = {
            "model": self._model,
            "messages": self._convert_messages(messages),
            "stream": False,
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
                f"{self._base_url}/api/chat",
                json=body,
                timeout=self._timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPStatusError as exc:
            raise OllamaError(f"Ollama API returned HTTP {exc.response.status_code}") from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise OllamaError("Ollama request failed") from exc
        finally:
            if owns_client:
                await client.aclose()

        return self._parse_response(payload)

    @staticmethod
    def _convert_messages(messages: Sequence[Message]) -> list[dict[str, Any]]:
        conversation: list[dict[str, Any]] = []
        for message in messages:
            if message.role == "tool":
                if not message.tool_name:
                    raise ValueError("Ollama tool results require a tool name")
                conversation.append({
                    "role": "tool",
                    "tool_name": message.tool_name,
                    "content": message.content,
                })
                continue
            if message.role not in ("system", "user", "assistant"):
                raise ValueError("unsupported message role")
            if message.role == "assistant" and message.provider_content:
                # Ollama's response message includes tool calls and sometimes
                # thinking. Return it unchanged with the tool result.
                if (
                    len(message.provider_content) != 1
                    or message.provider_content[0].get("role") != "assistant"
                ):
                    raise ValueError("invalid Ollama assistant content")
                conversation.append(dict(message.provider_content[0]))
                continue

            turn: dict[str, Any] = {"role": message.role, "content": message.content}
            if message.role == "assistant" and message.tool_calls:
                turn["tool_calls"] = [
                    {
                        "type": "function",
                        "function": {"name": call.name, "arguments": call.arguments},
                    }
                    for call in message.tool_calls
                ]
            if not message.content and not turn.get("tool_calls"):
                raise ValueError("conversation messages must have content or tool calls")
            conversation.append(turn)
        return conversation

    @staticmethod
    def _parse_response(payload: Any) -> LLMResponse:
        if not isinstance(payload, dict) or payload.get("done") is not True:
            raise OllamaError("Ollama returned an incomplete response")
        if payload.get("done_reason") == "length":
            raise OllamaError("Ollama response reached the output token limit")
        message = payload.get("message")
        if not isinstance(message, dict) or message.get("role") != "assistant":
            raise OllamaError("Ollama returned an invalid assistant message")
        content = message.get("content")
        if not isinstance(content, str):
            raise OllamaError("Ollama returned invalid text")
        raw_calls = message.get("tool_calls", [])
        if raw_calls is None:
            raw_calls = []
        if not isinstance(raw_calls, list):
            raise OllamaError("Ollama returned invalid tool calls")
        calls: list[FunctionCall] = []
        for raw_call in raw_calls:
            if not isinstance(raw_call, dict) or not isinstance(raw_call.get("function"), dict):
                raise OllamaError("Ollama returned an invalid tool call")
            function = raw_call["function"]
            name, arguments = function.get("name"), function.get("arguments")
            if not isinstance(name, str) or not name or not isinstance(arguments, dict):
                raise OllamaError("Ollama returned an invalid tool call")
            calls.append(FunctionCall(name=name, arguments=arguments))
        if not content and not calls:
            raise OllamaError("Ollama returned an empty response")
        model = payload.get("model")
        if not isinstance(model, str) or not model:
            raise OllamaError("Ollama returned an invalid model ID")
        return LLMResponse(
            content=content,
            function_calls=tuple(calls),
            finish_reason=payload.get("done_reason"),
            model=model,
            provider_content=(message,),
        )
