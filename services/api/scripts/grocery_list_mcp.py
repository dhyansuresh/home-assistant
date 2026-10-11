"""End-to-end check of the grocery list through the real runtime MCP server and SQLite.

Run from services/api; it uses a throwaway database and needs no API keys or running server:
    python scripts/grocery_list_mcp.py
"""

from __future__ import annotations

import asyncio
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import GroceryListRepository  # noqa: E402
from app.runtime_mcp_client import MCPGroceryList, MCPToolError  # noqa: E402


def check(label: str, ok: bool, detail: object = "") -> bool:
    print(f"{label}: {'PASS' if ok else 'FAIL'}{f' — {detail}' if detail != '' else ''}")
    return ok


def looks_saved(item: dict) -> bool:
    try:
        UUID(item["id"])
        stamped = datetime.fromisoformat(item["created_at"]).tzinfo is not None
    except (KeyError, TypeError, ValueError):
        return False
    return stamped and item["name"] == "Test milk" and item["quantity"] == 2


async def main() -> int:
    results: list[bool] = []
    with tempfile.TemporaryDirectory(prefix="homepilot-mcp-check-") as folder:
        path = Path(folder) / "list.sqlite3"
        repository = GroceryListRepository(path)
        repository.create_schema()
        repository.create_schema()
        results.append(check("schema can be created twice", path.is_file()))

        mcp = MCPGroceryList(path)
        results.append(check("empty list over MCP", await mcp.get_grocery_list() == []))

        saved = await mcp.add_grocery_list_item("Test milk", 2)
        results.append(check("add over MCP", looks_saved(saved), saved))
        results.append(check("read back over MCP", await mcp.get_grocery_list() == [saved]))
        results.append(check("row is in SQLite", repository.list_items() == [saved]))

        try:
            await mcp.add_grocery_list_item("   ", 1)
            refused = False
        except MCPToolError:
            refused = True
        results.append(check("blank name refused", refused))
        results.append(check("refused write changed nothing", repository.list_items() == [saved]))

    print(f"\nSummary: {sum(results)}/{len(results)} checks passed")
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
