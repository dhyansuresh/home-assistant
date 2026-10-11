"""Call the runtime MCP server's grocery-list tools from the API process."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from mcp import Client, StdioServerParameters

from app.settings import REPOSITORY_ROOT

SERVER_SCRIPT = REPOSITORY_ROOT / "services" / "runtime_mcp" / "server.py"
# Only these variables reach the child process, plus the database path.
_PASSED_ENVIRONMENT = ("PATH", "HOME", "TMPDIR", "TEMP", "TMP", "SYSTEMROOT", "WINDIR", "VIRTUAL_ENV", "PYTHONPATH")
TOOL_TIMEOUT_SECONDS = 15.0


class MCPToolError(RuntimeError):
    """The MCP tool failed or answered with something other than one JSON object."""


class MCPGroceryList:
    """Grocery-list store whose reads and writes go through the runtime MCP tools."""

    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path)

    async def get_grocery_list(self) -> list[dict[str, Any]]:
        payload = await self._call("get_grocery_list", {})
        if not isinstance(payload.get("items"), list):
            raise MCPToolError("get_grocery_list did not return an item list")
        return payload["items"]

    async def add_grocery_list_item(self, name: str, quantity: int) -> dict[str, Any]:
        payload = await self._call("add_grocery_list_item", {"name": name, "quantity": quantity})
        if not isinstance(payload.get("item"), dict):
            raise MCPToolError("add_grocery_list_item did not return the saved item")
        return payload["item"]

    async def _call(self, tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
        environment = {key: os.environ[key] for key in _PASSED_ENVIRONMENT if key in os.environ}
        environment["HOME_PILOT_DATABASE_PATH"] = str(self.database_path)
        parameters = StdioServerParameters(command=sys.executable, args=[str(SERVER_SCRIPT)], env=environment)
        async with Client(parameters) as client:
            result = await client.call_tool(tool, arguments, read_timeout_seconds=TOOL_TIMEOUT_SECONDS)
        if result.is_error:
            raise MCPToolError(f"{tool} failed")
        texts = [block.text for block in result.content if getattr(block, "text", None) is not None]
        try:
            (text,) = texts
            payload = json.loads(text)
        except ValueError as error:
            raise MCPToolError(f"{tool} returned an unreadable result") from error
        if not isinstance(payload, dict):
            raise MCPToolError(f"{tool} returned an unreadable result")
        return payload
