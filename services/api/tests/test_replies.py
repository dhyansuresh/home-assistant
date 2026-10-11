import asyncio

import pytest

from app.llm_interface import FunctionCall, LLMResponse
from app.orchestrator import CommandValidationError, Orchestrator
from app.vision_service import RecognitionResponse
from app.vlm_interface import VLMRequest
from tests.test_scan_confirmation import PHOTO, VALID, Clock, MemoryStore, ScriptedLLM


def add(name: str, quantity: int) -> FunctionCall:
    return FunctionCall(name="add_grocery_list_item", arguments={"name": name, "quantity": quantity})


READ = LLMResponse(content="", function_calls=(FunctionCall(name="get_grocery_list", arguments={}),))


class RecognisedVision:
    async def describe(self, request: VLMRequest) -> RecognitionResponse:
        recognition = {"recognition_id": "r", "model_id": "m", "unknown": False, "requires_confirmation": True,
                       "candidates": [{"name": "Peanut Chocolate Candies", "brand": "M&M's", "size_label": None,
                                       "rank": 1, "score": 3.1}]}
        return RecognitionResponse(description="ranked candidates…", recognition=recognition)


def test_list_is_one_item_per_line_with_repeats_combined_and_no_extra_llm_call() -> None:
    store = MemoryStore()
    store.items = [{"name": "milk", "quantity": 2}, {"name": "Milk", "quantity": 1}, {"name": "bananas", "quantity": 3}]
    result = asyncio.run(Orchestrator(ScriptedLLM(VALID, READ), grocery_list_store=store).run("show my list"))
    assert result.response == "Your grocery list has 2 items:\n• Milk × 3\n• Bananas × 3"


def test_empty_list_reply() -> None:
    result = asyncio.run(Orchestrator(ScriptedLLM(VALID, READ), grocery_list_store=MemoryStore()).run("show my list"))
    assert result.response == "Your grocery list is empty."


def test_several_named_items_are_all_added() -> None:
    store = MemoryStore()
    turn = LLMResponse(content="", function_calls=(add("eggs", 12), add("bread", 1)))
    result = asyncio.run(Orchestrator(ScriptedLLM(VALID, turn), grocery_list_store=store).run("add eggs and bread"))
    assert result.status == "completed"
    assert [(item["name"], item["quantity"]) for item in store.items] == [("eggs", 12), ("bread", 1)]
    assert result.response == "Added eggs × 12 and bread × 1 to your grocery list."


def test_invalid_item_in_a_batch_saves_nothing() -> None:
    store = MemoryStore()
    turn = LLMResponse(content="", function_calls=(add("eggs", 1), add("bread", 0)))
    with pytest.raises(CommandValidationError):
        asyncio.run(Orchestrator(ScriptedLLM(VALID, turn), grocery_list_store=store).run("add eggs and bread"))
    assert store.items == []


def test_photo_question_answers_with_top_match_and_yes_adds_it() -> None:
    store = MemoryStore()
    bot = Orchestrator(ScriptedLLM(VALID, LLMResponse(content="Not sure, please confirm.")), RecognisedVision(),
                       grocery_list_store=store, clock=Clock())
    asked = asyncio.run(bot.run("What is this?", image=PHOTO))
    assert asked.status == "in_progress"
    assert asked.response.startswith("That looks like M&M's Peanut Chocolate Candies.")
    done = asyncio.run(bot.run("yes"))
    assert done.response == "Added M&M's Peanut Chocolate Candies × 1 to your grocery list."
    assert len(store.items) == 1
