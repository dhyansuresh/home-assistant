import asyncio
import json

import httpx
import pytest

from app.llm_interface import FunctionCall, FunctionDefinition, Message
from app.ollama import OllamaError, OllamaProvider

GET_LIST = FunctionDefinition(name="get_grocery_list", description="Read the list.", parameters={"type": "object"})


def provider(handler) -> OllamaProvider:
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return OllamaProvider("http://ollama.test", "qwen3:8b", http_client=client)


def test_sends_tools_without_thinking_and_parses_tool_calls() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"], seen["body"] = request.url.path, json.loads(request.content)
        return httpx.Response(200, json={
            "model": "qwen3:8b", "done_reason": "stop",
            "message": {"role": "assistant", "content": "",
                        "tool_calls": [{"function": {"name": "get_grocery_list", "arguments": {}}}]},
        })

    response = asyncio.run(provider(handler).complete([Message(role="user", content="show my list")],
                                                      functions=[GET_LIST], temperature=0))

    assert seen["path"] == "/api/chat"
    assert seen["body"]["think"] is False and seen["body"]["stream"] is False
    assert seen["body"]["tools"][0]["function"]["name"] == "get_grocery_list"
    assert seen["body"]["options"] == {"temperature": 0}
    assert response.function_calls == (FunctionCall(name="get_grocery_list", arguments={}),)


def test_tool_result_round_trip_uses_tool_role() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["messages"] = json.loads(request.content)["messages"]
        return httpx.Response(200, json={"model": "qwen3:8b", "message": {"role": "assistant", "content": "Milk x2"}})

    call = FunctionCall(name="get_grocery_list", arguments={})
    response = asyncio.run(provider(handler).complete([
        Message(role="system", content="Report the result."),
        Message(role="assistant", content="", tool_calls=(call,)),
        Message(role="tool", tool_name="get_grocery_list", content='{"items": []}'),
    ]))

    assert [m["role"] for m in seen["messages"]] == ["system", "assistant", "tool"]
    assert seen["messages"][1]["tool_calls"] == [{"function": {"name": "get_grocery_list", "arguments": {}}}]
    assert seen["messages"][2]["tool_name"] == "get_grocery_list"
    assert response.content == "Milk x2"


@pytest.mark.parametrize("status, body", [(500, {"error": "boom"}), (200, {"unexpected": True})])
def test_failures_raise_ollama_error(status: int, body: dict) -> None:
    with pytest.raises(OllamaError):
        asyncio.run(provider(lambda request: httpx.Response(status, json=body)).complete(
            [Message(role="user", content="hi")]))


def test_unreachable_server_raises_ollama_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    with pytest.raises(OllamaError):
        asyncio.run(provider(handler).complete([Message(role="user", content="hi")]))
