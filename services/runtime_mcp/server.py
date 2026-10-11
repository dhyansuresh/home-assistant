"""HomePilot runtime MCP server: grocery-list tools over stdio.

The FastAPI backend starts this process per tool call. The database location comes from the
HOME_PILOT_DATABASE_PATH environment variable set by that caller, never from tool arguments.
"""

import json
import sys
from pathlib import Path

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "services" / "api"))

from app.database import GroceryListRepository  # noqa: E402

repository = GroceryListRepository()
repository.create_schema()
server = MCPServer("homepilot-runtime")


@server.tool()
def get_grocery_list() -> str:
    """List every item on the household grocery list."""
    return json.dumps({"items": repository.list_items()}, ensure_ascii=False)


@server.tool()
def add_grocery_list_item(name: str, quantity: int) -> str:
    """Put an item on the grocery list. ``quantity`` must be a positive whole number."""
    try:
        item = repository.add_item(name, quantity)
    except ValueError as error:
        raise ToolError(str(error)) from error
    return json.dumps({"item": item}, ensure_ascii=False)


if __name__ == "__main__":
    server.run(transport="stdio")
