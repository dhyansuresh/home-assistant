import asyncio

from app.database import GroceryListRepository
from app.llm_interface import FunctionCall, LLMResponse
from app.orchestrator import Orchestrator
from tests.test_scan_confirmation import VALID, Clock, MemoryStore, ScriptedLLM

CLEAR = LLMResponse(content="", function_calls=(FunctionCall(name="clear_grocery_list", arguments={}),))


def remove(*names: str) -> LLMResponse:
    return LLMResponse(content="", function_calls=tuple(
        FunctionCall(name="remove_grocery_list_item", arguments={"name": n}) for n in names))


def stocked() -> MemoryStore:
    store = MemoryStore()
    store.items = [{"name": "milk", "quantity": 2}, {"name": "Milk", "quantity": 1}, {"name": "bananas", "quantity": 3}]
    return store


def test_repository_removes_any_capitalisation_and_plural_then_clears(tmp_path) -> None:
    repo = GroceryListRepository(tmp_path / "list.sqlite3")
    repo.create_schema()
    for name, quantity in [("milk", 2), ("Milk", 1), ("bananas", 3), ("eggs", 1)]:
        repo.add_item(name, quantity)
    assert repo.remove_item("MILK")["removed"] == 3
    assert repo.remove_item("banana")["removed"] == 3
    assert repo.remove_item("bread")["removed"] == 0
    assert [i["name"] for i in repo.list_items()] == ["eggs"]
    assert repo.clear_items() == {"cleared": 1}
    assert repo.list_items() == []


def test_remove_named_items() -> None:
    store = stocked()
    result = asyncio.run(Orchestrator(ScriptedLLM(VALID, remove("milk", "bread")), grocery_list_store=store).run(
        "I bought milk and bread"))
    assert result.response == "Removed milk from your grocery list. Bread wasn't on your list."
    assert [i["name"] for i in store.items] == ["bananas"]


def test_clear_asks_first_and_only_yes_empties_the_list() -> None:
    store = stocked()
    bot = Orchestrator(ScriptedLLM(VALID, CLEAR), grocery_list_store=store, clock=Clock())
    asked = asyncio.run(bot.run("clear my list"))
    assert asked.status == "in_progress"
    assert asked.response.startswith("Should I clear all 2 items")
    assert len(store.items) == 3
    done = asyncio.run(bot.run("yes"))
    assert done.response == "Done. I cleared all 2 items from your grocery list."
    assert store.items == []


def test_clear_then_no_keeps_the_list() -> None:
    store = stocked()
    bot = Orchestrator(ScriptedLLM(VALID, CLEAR), grocery_list_store=store, clock=Clock())
    asyncio.run(bot.run("clear my list"))
    assert asyncio.run(bot.run("no")).response == "Okay, I kept your grocery list as it is."
    assert len(store.items) == 3


def test_clearing_an_empty_list_needs_no_confirmation() -> None:
    bot = Orchestrator(ScriptedLLM(VALID, CLEAR), grocery_list_store=MemoryStore(), clock=Clock())
    assert asyncio.run(bot.run("clear my list")).response == "Your grocery list is already empty."
    assert bot.pending is None
