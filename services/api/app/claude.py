"""Claude Messages API implementation of the shared LLM provider interface."""

from __future__ import annotations

import os
from typing import Any, Sequence

import httpx

from app.llm_interface import FunctionCall, FunctionDefinition, LLMResponse, Message
from app.settings import load_local_environment

CLAUDE_API_URL = "https://api.anthropic.com/v1/messages"
CLAUDE_API_VERSION = "2023-06-01"
DEFAULT_MODEL = "claude-sonnet-5-5"
DEFAULT_MAX_TOKENS = 4096


class ClaudeError(RuntimeError):
    """Raised when Claude is unavailable or returns an unusable response."""


class ClaudeProvider:
    """Translate orchestrator turns and tool calls to the Claude Messages API."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        *,
        max_tokens: int | None = None,
        timeout_seconds: float = 60.0,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        load_local_environment()
        self._api_key = api_key if api_key is not None else os.getenv("ANTHROPIC_API_KEY")
        self._model = model if model is not None else os.getenv("CLAUDE_MODEL", DEFAULT_MODEL)
        if not self._model.strip():
            raise ValueError("CLAUDE_MODEL must not be blank")
        configured_tokens = max_tokens if max_tokens is not None else os.getenv(
            "CLAUDE_MAX_TOKENS", str(DEFAULT_MAX_TOKENS)
        )
        try:
            self._max_tokens = int(configured_tokens)
        except (TypeError, ValueError) as exc:
            raise ValueError("CLAUDE_MAX_TOKENS must be a positive integer") from exc
        if self._max_tokens < 1:
            raise ValueError("CLAUDE_MAX_TOKENS must be a positive integer")
        self._timeout_seconds = timeout_seconds
        self._http_client = http_client

    async def complete(
        self,
        messages: Sequence[Message],
        *,
        functions: Sequence[FunctionDefinition] = (),
        temperature: float | None = None,
    ) -> LLMResponse:
        if not self._api_key:
            raise ClaudeError("ANTHROPIC_API_KEY is not configured")
        if not messages:
            raise ValueError("messages must include at least one conversation turn")

        conversation, system = self._convert_messages(messages)
        body: dict[str, Any] = {
            "model": self._model,
            "max_tokens": self._max_tokens,
            "messages": conversation,
        }
        if system:
            body["system"] = system
        if functions:
            body["tools"] = [
                {"name": fn.name, "description": fn.description, "input_schema": fn.parameters}
                for fn in functions
            ]
        # Current Claude models reject non-default sampling temperatures. The
        # interface accepts this argument, but Claude uses its model default.
        _ = temperature

        owns_client = self._http_client is None
        client = self._http_client or httpx.AsyncClient(timeout=self._timeout_seconds)
        try:
            response = await client.post(
                CLAUDE_API_URL,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "anthropic-version": CLAUDE_API_VERSION,
                    "content-type": "application/json",
                },
                json=body,
                timeout=self._timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPStatusError as exc:
            raise ClaudeError(f"Claude API returned HTTP {exc.response.status_code}") from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise ClaudeError("Claude request failed") from exc
        finally:
            if owns_client:
                await client.aclose()

        return self._parse_response(payload)

    @staticmethod
    def _convert_messages(messages: Sequence[Message]) -> tuple[list[dict[str, Any]], str]:
        system = "\n\n".join(message.content for message in messages if message.role == "system")
        conversation: list[dict[str, Any]] = []
        for message in messages:
            if message.role == "system":
                continue
            if message.role == "tool":
                if not message.tool_call_id:
                    raise ClaudeError("Claude tool results require a tool call ID")
                conversation.append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": message.tool_call_id,
                        "content": message.content,
                    }],
                })
                continue
            if message.role not in ("user", "assistant"):
                raise ValueError("unsupported message role")

            if message.role == "assistant" and message.provider_content is not None:
                blocks = list(message.provider_content)
            else:
                blocks: list[dict[str, Any]] = []
                if message.content:
                    blocks.append({"type": "text", "text": message.content})
                if message.role == "assistant":
                    for call in message.tool_calls:
                        if not call.call_id:
                            raise ClaudeError("Claude tool calls require a tool call ID")
                        blocks.append({
                            "type": "tool_use", "id": call.call_id,
                            "name": call.name, "input": call.arguments,
                        })
            if not blocks:
                raise ValueError("conversation messages must have content or tool calls")
            conversation.append({"role": message.role, "content": blocks})
        if not conversation:
            raise ValueError("messages must contain at least one non-system turn")
        return conversation, system

    def _parse_response(self, payload: Any) -> LLMResponse:
        if not isinstance(payload, dict) or not isinstance(payload.get("content"), list):
            raise ClaudeError("Claude returned an invalid response")
        stop_reason = payload.get("stop_reason")
        if stop_reason == "max_tokens":
            raise ClaudeError("Claude response reached the output token limit")
        if stop_reason not in ("end_turn", "stop_sequence", "tool_use", "refusal"):
            raise ClaudeError("Claude returned an unsupported stop reason")

        text_parts: list[str] = []
        calls: list[FunctionCall] = []
        for block in payload["content"]:
            if not isinstance(block, dict):
                raise ClaudeError("Claude returned an invalid content block")
            if block.get("type") == "text":
                if not isinstance(block.get("text"), str):
                    raise ClaudeError("Claude returned invalid text")
                text_parts.append(block["text"])
            elif block.get("type") == "tool_use":
                call_id, name, arguments = block.get("id"), block.get("name"), block.get("input")
                if not isinstance(call_id, str) or not call_id or not isinstance(name, str) \
                        or not name or not isinstance(arguments, dict):
                    raise ClaudeError("Claude returned an invalid tool call")
                calls.append(FunctionCall(name=name, arguments=arguments, call_id=call_id))
        if (stop_reason == "tool_use") != bool(calls) or (not text_parts and not calls):
            raise ClaudeError("Claude returned an incomplete response")
        model = payload.get("model")
        if not isinstance(model, str) or not model:
            raise ClaudeError("Claude returned an invalid model ID")
        return LLMResponse(
            content="".join(text_parts),
            function_calls=tuple(calls),
            finish_reason=stop_reason,
            model=model,
            provider_content=tuple(payload["content"]),
        )
