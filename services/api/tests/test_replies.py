import asyncio

import pytest

from app.llm_interface import FunctionCall, LLMResponse
from app.orchestrator import CommandValidationError, Orchestrator
from app.vision_service import RecognitionResponse
from app.vlm_interface import VLMRequest
from tests.test_scan_confirmation import PHOTO, RECOGNIZE, VALID, Clock, MemoryStore, ScriptedLLM


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


def test_photo_question_goes_through_recognition_and_yes_adds_the_agreed_match() -> None:
    store = MemoryStore()
    agree = LLMResponse(content="", function_calls=(add("M&M's Peanut Chocolate Candies", 1),))
    bot = Orchestrator(ScriptedLLM(VALID, RECOGNIZE, agree), RecognisedVision(),
                       grocery_list_store=store, clock=Clock())
    asked = asyncio.run(bot.run("What is this?", image=PHOTO))
    assert asked.status == "in_progress"
    assert asked.response.startswith("This looks like M&M's Peanut Chocolate Candies.")
    done = asyncio.run(bot.run("yes"))
    assert done.response == "Added M&M's Peanut Chocolate Candies × 1 to your grocery list."
    assert len(store.items) == 1


def test_named_item_with_a_photo_attached_is_added_without_recognition() -> None:
    """A webcam frame rides along with every voice command; "add milk" must not depend on it."""
    store = MemoryStore()
    bot = Orchestrator(ScriptedLLM(VALID, LLMResponse(content="", function_calls=(add("milk", 1),))),
                       RecognisedVision(), grocery_list_store=store, clock=Clock())
    result = asyncio.run(bot.run("add milk", image=PHOTO))
    assert result.response == "Added milk × 1 to your grocery list."
    assert [item["name"] for item in store.items] == ["milk"]


def test_disagreeing_with_the_photo_saves_nothing_and_asks() -> None:
    store = MemoryStore()
    ask = LLMResponse(content="That looks like M&M's Peanut Chocolate Candies, not milk. Which did you mean?")
    bot = Orchestrator(ScriptedLLM(VALID, RECOGNIZE, ask), RecognisedVision(), grocery_list_store=store, clock=Clock())
    result = asyncio.run(bot.run("add this milk", image=PHOTO))
    assert result.status == "in_progress" and store.items == [] and bot.pending is None


class UnknownVision:
    async def describe(self, request: VLMRequest) -> RecognitionResponse:
        recognition = {"recognition_id": "r", "model_id": "m", "unknown": True, "requires_confirmation": True,
                       "candidates": []}
        return RecognitionResponse(description="unknown", recognition=recognition)


def test_guessed_photo_add_without_recognition_is_checked_against_the_photo() -> None:
    """qwen skips recognize_photo and guesses "Red Bull" for "add this": the photo is checked first."""
    store = MemoryStore()
    guess = LLMResponse(content="", function_calls=(add("Red Bull", 1),))
    agree = LLMResponse(content="", function_calls=(add("M&M's Peanut Chocolate Candies", 1),))
    bot = Orchestrator(ScriptedLLM(VALID, guess, agree), RecognisedVision(), grocery_list_store=store, clock=Clock())
    result = asyncio.run(bot.run("add this", image=PHOTO))
    assert store.items == [] and result.status == "in_progress"
    assert result.response.startswith("This looks like M&M's Peanut Chocolate Candies.")


def test_unknown_photo_never_becomes_a_proposal() -> None:
    store = MemoryStore()
    guess = LLMResponse(content="", function_calls=(add("Red Bull", 1),))
    bot = Orchestrator(ScriptedLLM(VALID, RECOGNIZE, guess), UnknownVision(), grocery_list_store=store, clock=Clock())
    result = asyncio.run(bot.run("add this", image=PHOTO))
    assert result.response == "I couldn't recognize that item. What is it called?"
    assert bot.pending is None and store.items == []


def test_extra_items_after_a_photo_are_mentioned_not_dropped_silently() -> None:
    both = LLMResponse(content="", function_calls=(add("M&M's Peanut Chocolate Candies", 1), add("milk", 1)))
    bot = Orchestrator(ScriptedLLM(VALID, RECOGNIZE, both), RecognisedVision(), grocery_list_store=MemoryStore(),
                       clock=Clock())
    result = asyncio.run(bot.run("add this and milk", image=PHOTO))
    assert result.response.endswith("I can add one photo item at a time.")


@pytest.mark.parametrize("prompt, expected", [
    ("add this 7up", 1), ("add this 500 ml one", 1), ("add two of these", 2), ("add 3 of these", 3), ("add this", 1),
])
def test_photo_quantity_only_comes_from_a_count_before_these(prompt: str, expected: int) -> None:
    from app.orchestrator import _photo_quantity

    assert _photo_quantity(prompt) == expected


@pytest.mark.parametrize("prompt, about_photo", [
    ("add milk, that's all", False), ("what's on my list?", False), ("add it", False),
    ("what is this?", True), ("add these", True), ("add that one", True),
    ("what is it?", True), ("what am I holding?", True),
])
def test_only_pointing_words_refer_to_the_photo(prompt: str, about_photo: bool) -> None:
    from app.orchestrator import _refers_to_photo

    assert _refers_to_photo(prompt) is about_photo


def test_malformed_add_arguments_are_a_validation_error_not_a_crash() -> None:
    bad = LLMResponse(content="", function_calls=(FunctionCall(name="add_grocery_list_item", arguments="milk"),))
    with pytest.raises(CommandValidationError):
        asyncio.run(Orchestrator(ScriptedLLM(VALID, bad), RecognisedVision(), grocery_list_store=MemoryStore(),
                                 clock=Clock()).run("add this", image=PHOTO))


def test_named_item_beside_a_guessed_photo_item_is_kept() -> None:
    store = MemoryStore()
    first = LLMResponse(content="", function_calls=(add("Red Bull", 1), add("milk", 1)))
    agree = LLMResponse(content="", function_calls=(add("M&M's Peanut Chocolate Candies", 1),))
    bot = Orchestrator(ScriptedLLM(VALID, first, agree), RecognisedVision(), grocery_list_store=store, clock=Clock())
    result = asyncio.run(bot.run("add this and milk", image=PHOTO))
    assert [item["name"] for item in store.items] == ["milk"]
    assert result.response.startswith("Added milk × 1 to your grocery list. This looks like M&M's Peanut")


def test_what_is_this_counts_as_agreeing_with_the_photo() -> None:
    """qwen answers in text after recognising; the photo still becomes the yes/no proposal."""
    store = MemoryStore()
    text = LLMResponse(content="The photo shows M&M's Peanut Chocolate Candies. Would you like to add it?")
    bot = Orchestrator(ScriptedLLM(VALID, RECOGNIZE, text), RecognisedVision(), grocery_list_store=store, clock=Clock())
    asked = asyncio.run(bot.run("What is this?", image=PHOTO))
    assert asked.response.startswith("This looks like M&M's Peanut Chocolate Candies.")
    assert asyncio.run(bot.run("yes")).response == "Added M&M's Peanut Chocolate Candies × 1 to your grocery list."
