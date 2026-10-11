"""HomePilot runtime MCP tools for grocery-list access."""

import json
import sys
from pathlib import Path

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
API_SOURCE = REPOSITORY_ROOT / "services" / "api"
if str(API_SOURCE) not in sys.path:
    sys.path.insert(0, str(API_SOURCE))

from app.database import ShoppingListDatabase  # noqa: E402

mcp = MCPServer("homepilot-runtime")
database = ShoppingListDatabase()
database.initialize()


@mcp.tool()
def get_grocery_list() -> str:
    """Return the current grocery list."""
    return json.dumps({"items": database.get_grocery_list()}, ensure_ascii=False)


@mcp.tool()
def add_grocery_list_item(name: str, quantity: int) -> str:
    """Add a grocery-list item with a positive whole-number quantity."""
    if not isinstance(name, str) or not name.strip() or len(name.strip()) > 160:
        raise ToolError("name must be 1 to 160 nonblank characters")
    if type(quantity) is not int or quantity < 1:
        raise ToolError("quantity must be a positive integer")
    item = database.add_grocery_list_item(name.strip(), quantity)
    return json.dumps({"item": item}, ensure_ascii=False)

if __name__ == "__main__":
    mcp.run(transport="stdio")
