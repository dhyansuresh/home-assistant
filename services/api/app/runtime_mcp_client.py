"""stdio client for the HomePilot runtime grocery-list MCP tools."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from mcp import Client, StdioServerParameters

from app.settings import REPOSITORY_ROOT


class RuntimeMCPGroceryListClient:
    """Invoke grocery-list operations through the local runtime MCP server."""

    def __init__(self, database_path: str | Path) -> None:
        self._server_path = REPOSITORY_ROOT / "services" / "runtime_mcp" / "server.py"
        self._database_path = str(database_path)

    async def get_grocery_list(self) -> list[dict[str, Any]]:
        result = await self._call("get_grocery_list", {})
        items = result.get("items")
        if not isinstance(items, list):
            raise RuntimeError("runtime MCP returned an invalid grocery list")
        return items

    async def add_grocery_list_item(self, name: str, quantity: int) -> dict[str, Any]:
        result = await self._call(
            "add_grocery_list_item", {"name": name, "quantity": quantity}
        )
        item = result.get("item")
        if not isinstance(item, dict):
            raise RuntimeError("runtime MCP returned an invalid grocery-list item")
        return item

    async def _call(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        environment = {
            key: os.environ[key]
            for key in ("PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "VIRTUAL_ENV", "PYTHONPATH")
            if key in os.environ
        }
        environment["HOME_PILOT_DATABASE_PATH"] = self._database_path
        server_parameters = StdioServerParameters(
            command=sys.executable,
            args=[str(self._server_path)],
            env=environment,
        )
        async with Client(server_parameters) as client:
            response = await client.call_tool(
                name, arguments, read_timeout_seconds=15.0
            )
        if response.is_error:
            raise RuntimeError(f"runtime MCP tool {name} failed")
        text_blocks = [block.text for block in response.content if hasattr(block, "text")]
        if len(text_blocks) != 1:
            raise RuntimeError(f"runtime MCP tool {name} returned an invalid response")
        payload = json.loads(text_blocks[0])
        if not isinstance(payload, dict):
            raise RuntimeError(f"runtime MCP tool {name} returned an invalid response")
        return payload
