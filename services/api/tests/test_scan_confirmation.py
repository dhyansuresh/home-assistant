import asyncio
import json
from typing import Any, Sequence

import pytest

from app.llm_interface import FunctionCall, FunctionDefinition, LLMResponse, Message
from app.orchestrator import PENDING_CONFIRMATION_SECONDS, Orchestrator
from app.vlm_interface import VLMRequest, VLMResponse

VALID = LLMResponse(content=json.dumps({"valid": True, "reason": None}))
ADD_WATER = LLMResponse(content="", function_calls=(
    FunctionCall(name="add_grocery_list_item", arguments={"name": "Purified Water 40-Pack", "quantity": 1}),
))
PHOTO = VLMRequest(image=b"photo bytes", content_type="image/jpeg")
# The LLM asks for the photo to be recognised before deciding (recognize_photo tool).
RECOGNIZE = LLMResponse(content="", function_calls=(FunctionCall(name="recognize_photo", arguments={}),))


class ScriptedLLM:
    """Return queued responses in order; fail if the orchestrator asks for more."""

    def __init__(self, *responses: LLMResponse) -> None:
        self.responses = list(responses)

    async def complete(self, messages: Sequence[Message], *, functions: Sequence[FunctionDefinition] = (),
                       temperature: float | None = None) -> LLMResponse:
        assert self.responses, "unexpected LLM call"
        return self.responses.pop(0)


class FixedVision:
    async def describe(self, request: VLMRequest) -> VLMResponse:
        from app.vision_service import RecognitionResponse

        recognition = {"recognition_id": "r", "model_id": "m", "unknown": False, "requires_confirmation": True,
                       "candidates": [{"name": "Purified Water 40-Pack", "brand": None, "size_label": None,
                                       "rank": 1, "score": 0.9}]}
        return RecognitionResponse(description="Rank 1: Purified Water 40-Pack", recognition=recognition)


class MemoryStore:
    def __init__(self) -> None:
        self.items: list[dict[str, Any]] = []

    async def get_grocery_list(self) -> list[dict[str, Any]]:
        return list(self.items)

    async def add_grocery_list_item(self, name: str, quantity: int) -> dict[str, Any]:
        item = {"id": str(len(self.items) + 1), "name": name, "quantity": quantity, "created_at": "now"}
        self.items.append(item)
        return item

    async def remove_grocery_list_item(self, name: str) -> dict[str, Any]:
        keep = [i for i in self.items if i["name"].lower() not in {name.lower(), name.lower().rstrip("s"), name.lower() + "s"}]
        removed = sum(i["quantity"] for i in self.items if i not in keep)
        self.items = keep
        return {"name": name, "removed": removed}

    async def clear_grocery_list(self) -> dict[str, Any]:
        count, self.items = len(self.items), []
        return {"cleared": count}


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def orchestrator(llm: ScriptedLLM, store: MemoryStore, clock: Clock | None = None) -> Orchestrator:
    return Orchestrator(llm, FixedVision(), grocery_list_store=store, clock=clock or Clock())


def test_photo_add_asks_first_and_saves_only_after_yes() -> None:
    store = MemoryStore()
    bot = orchestrator(ScriptedLLM(VALID, RECOGNIZE, ADD_WATER), store)

    asked = asyncio.run(bot.run("add this to my list", image=PHOTO))
    assert asked.status == "in_progress"
    assert "Purified Water 40-Pack" in asked.response and "yes" in asked.response
    assert store.items == []

    done = asyncio.run(bot.run("Yes, please!"))
    assert done.status == "completed"
    assert [(i["name"], i["quantity"]) for i in store.items] == [("Purified Water 40-Pack", 1)]

    # The confirmation is consumed: a second yes does not add again (it goes through the normal flow).
    bot.llm = ScriptedLLM(LLMResponse(content=json.dumps({"valid": False, "reason": "Not a command."})))
    assert asyncio.run(bot.run("yes")).status == "rejected"
    assert len(store.items) == 1


@pytest.mark.parametrize("reply", ["no", "No thanks.", "cancel", "don't add it"])
def test_no_cancels_without_saving(reply: str) -> None:
    store = MemoryStore()
    bot = orchestrator(ScriptedLLM(VALID, RECOGNIZE, ADD_WATER), store)
    asyncio.run(bot.run("add this", image=PHOTO))

    result = asyncio.run(bot.run(reply))
    assert result.status == "completed" and "did not add" in result.response
    assert store.items == []


def test_other_request_or_expiry_discards_the_pending_add() -> None:
    store = MemoryStore()
    clock = Clock()
    bot = orchestrator(ScriptedLLM(VALID, RECOGNIZE, ADD_WATER), store, clock)
    asyncio.run(bot.run("add this", image=PHOTO))

    # "yes, but three" is not a plain confirmation: it is handled as a new request and the pending add is dropped.
    bot.llm = ScriptedLLM(VALID, LLMResponse(content="How many would you like?"))
    assert asyncio.run(bot.run("yes but make it three")).status == "in_progress"
    bot.llm = ScriptedLLM(LLMResponse(content=json.dumps({"valid": False, "reason": "Not a command."})))
    asyncio.run(bot.run("yes"))
    assert store.items == []

    bot.llm = ScriptedLLM(VALID, RECOGNIZE, ADD_WATER)
    asyncio.run(bot.run("add this", image=PHOTO))
    clock.now += PENDING_CONFIRMATION_SECONDS + 1
    bot.llm = ScriptedLLM(LLMResponse(content=json.dumps({"valid": False, "reason": "Not a command."})))
    assert asyncio.run(bot.run("yes")).status == "rejected"
    assert store.items == []


def test_named_item_without_photo_is_saved_directly() -> None:
    store = MemoryStore()
    add_milk = LLMResponse(content="", function_calls=(
        FunctionCall(name="add_grocery_list_item", arguments={"name": "milk", "quantity": 2}),
    ))
    bot = orchestrator(ScriptedLLM(VALID, add_milk, LLMResponse(content="Added 2 milk.")), store)

    result = asyncio.run(bot.run("add 2 milk to my grocery list"))
    assert result.status == "completed"
    assert [(i["name"], i["quantity"]) for i in store.items] == [("milk", 2)]
