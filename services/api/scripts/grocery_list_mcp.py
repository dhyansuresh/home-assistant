"""Exercise SQLite grocery-list persistence through the runtime MCP tools.

Run from ``services/api`` after installing its requirements:
    python scripts/grocery_list_mcp.py

The script uses a temporary database and does not need API keys or a running
FastAPI server.
"""

from __future__ import annotations

import asyncio
import sys
import tempfile
import uuid
from datetime import datetime
from pathlib import Path

# Allow direct execution as a script from services/api without installation.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import ShoppingListDatabase
from app.runtime_mcp_client import RuntimeMCPGroceryListClient


def report(name: str, passed: bool, detail: str = "") -> bool:
    outcome = "PASS" if passed else "FAIL"
    suffix = f" — {detail}" if detail else ""
    print(f"{name}: {outcome}{suffix}")
    return passed


async def main() -> int:
    checks: list[bool] = []
    with tempfile.TemporaryDirectory(prefix="homepilot-grocery-list-") as temporary_directory:
        database_path = Path(temporary_directory) / "grocery-list.sqlite3"
        database = ShoppingListDatabase(database_path)

        try:
            database.initialize()
            database.initialize()
            checks.append(
                report("SQLite table initialization", database_path.is_file(), "created and safe to initialize twice")
            )

            mcp_client = RuntimeMCPGroceryListClient(database_path)
            initial_items = await mcp_client.get_grocery_list()
            checks.append(report("MCP get on empty list", initial_items == [], f"items={initial_items}"))

            added_item = await mcp_client.add_grocery_list_item("Test milk", 2)
            valid_id = False
            try:
                uuid.UUID(added_item["id"])
                valid_id = True
            except (KeyError, TypeError, ValueError):
                pass
            timestamp = datetime.fromisoformat(added_item["created_at"])
            valid_item = (
                valid_id
                and added_item.get("name") == "Test milk"
                and added_item.get("quantity") == 2
                and timestamp.tzinfo is not None
            )
            checks.append(report("MCP add item", valid_item, f"item={added_item}"))

            listed_items = await mcp_client.get_grocery_list()
            round_trip_ok = listed_items == [added_item]
            checks.append(report("MCP get after add", round_trip_ok, f"items={listed_items}"))

            persisted_items = database.get_grocery_list()
            persisted_ok = persisted_items == [added_item]
            checks.append(report("SQLite persisted result", persisted_ok, f"items={persisted_items}"))

            rejected_invalid_write = False
            try:
                await mcp_client.add_grocery_list_item("   ", 1)
            except RuntimeError:
                rejected_invalid_write = True
            checks.append(
                report("MCP rejects blank item name", rejected_invalid_write)
            )

            unchanged_after_rejection = await mcp_client.get_grocery_list() == [added_item]
            checks.append(
                report("Rejected write leaves database unchanged", unchanged_after_rejection)
            )
        except Exception as exc:
            checks.append(report("MCP/database integration", False, f"{type(exc).__name__}: {exc}"))

    passed = sum(checks)
    print(f"\nSummary: {passed}/{len(checks)} checks passed")
    return 0 if checks and all(checks) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
