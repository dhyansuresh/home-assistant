"""Gemini implementation of the provider-neutral orchestrator interface."""

from __future__ import annotations

import json
import os
from typing import Any, Sequence
from urllib.parse import quote

import httpx

from app.llm_interface import FunctionCall, FunctionDefinition, LLMResponse, Message
from app.settings import load_local_environment

GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"


class GeminiError(RuntimeError):
    """Raised when Gemini is unavailable or returns an invalid response."""


class GeminiProvider:
    """Translate common orchestrator messages to Gemini's generateContent API."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        *,
        timeout_seconds: float = 30.0,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        load_local_environment()
        self._api_key = api_key or os.getenv("GEMINI_API_KEY")
        self._model = model or os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
        self._timeout_seconds = timeout_seconds
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
        if not self._api_key:
            raise GeminiError("GEMINI_API_KEY is not configured")
        if not messages:
            raise ValueError("messages must include at least one conversation turn")

        contents, system_instruction = self._convert_messages(messages)
        body: dict[str, Any] = {"contents": contents}
        if system_instruction:
            body["systemInstruction"] = {"parts": [{"text": system_instruction}]}
        if functions:
            body["tools"] = [{
                "functionDeclarations": [
                    {
                        "name": fn.name,
                        "description": fn.description,
                        "parameters": fn.parameters,
                    }
                    for fn in functions
                ]
            }]
        if temperature is not None:
            body["generationConfig"] = {"temperature": temperature}

        url = f"{GEMINI_API_BASE}/{quote(self._model, safe='')}:generateContent"
        owns_client = self._http_client is None
        client = self._http_client or httpx.AsyncClient(timeout=self._timeout_seconds)
        try:
            response = await client.post(
                url,
                headers={"x-goog-api-key": self._api_key},
                json=body,
                timeout=self._timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise GeminiError("Gemini request failed") from exc
        finally:
            if owns_client:
                await client.aclose()

        try:
            candidate = payload["candidates"][0]
            parts = candidate["content"]["parts"]
            if not isinstance(parts, list) or not all(isinstance(part, dict) for part in parts):
                raise ValueError("invalid response parts")
            text = "".join(part["text"] for part in parts if isinstance(part.get("text"), str))
            calls = tuple(
                FunctionCall(
                    name=part["functionCall"]["name"],
                    arguments=part["functionCall"].get("args", {}),
                    call_id=part["functionCall"].get("id"),
                )
                for part in parts
                if isinstance(part.get("functionCall"), dict)
            )
            if any(not call.name or not isinstance(call.arguments, dict) for call in calls):
                raise ValueError("invalid function call")
            return LLMResponse(
                content=text,
                function_calls=calls,
                finish_reason=candidate.get("finishReason"),
                model=self._model,
            )
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise GeminiError("Gemini returned an invalid or empty response") from exc

    @staticmethod
    def _convert_messages(messages: Sequence[Message]) -> tuple[list[dict[str, Any]], str]:
        system_text = "\n\n".join(message.content for message in messages if message.role == "system")
        contents: list[dict[str, Any]] = []
        for message in messages:
            if message.role == "system":
                continue
            if message.role == "tool":
                if not message.tool_name:
                    raise ValueError("tool messages require tool_name")
                try:
                    result: Any = json.loads(message.content)
                except json.JSONDecodeError:
                    result = {"result": message.content}
                function_response: dict[str, Any] = {"name": message.tool_name, "response": result}
                if message.tool_call_id:
                    function_response["id"] = message.tool_call_id
                contents.append({
                    "role": "function",
                    "parts": [{"functionResponse": function_response}],
                })
                continue

            parts: list[dict[str, Any]] = []
            if message.content:
                parts.append({"text": message.content})
            for call in message.tool_calls:
                function_call: dict[str, Any] = {"name": call.name, "args": call.arguments}
                if call.call_id:
                    function_call["id"] = call.call_id
                parts.append({"functionCall": function_call})
            if not parts:
                raise ValueError("conversation messages must have content or function calls")
            contents.append({
                "role": "model" if message.role == "assistant" else "user",
                "parts": parts,
            })
        if not contents:
            raise ValueError("messages must contain at least one non-system turn")
        return contents, system_text
