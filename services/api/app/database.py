"""SQLite persistence for HomePilot's grocery list."""

from __future__ import annotations

import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.settings import REPOSITORY_ROOT


class ShoppingListDatabase:
    """Small SQLite repository used by the orchestrator's grocery-list tools."""

    def __init__(self, path: str | Path | None = None) -> None:
        configured_path = path or os.getenv(
            "HOME_PILOT_DATABASE_PATH", str(REPOSITORY_ROOT / "data" / "homepilot.sqlite3")
        )
        self.path = Path(configured_path).expanduser()

    def initialize(self) -> None:
        """Create the shopping-list table if it does not exist yet."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """CREATE TABLE IF NOT EXISTS grocery_list_items (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL CHECK(length(trim(name)) BETWEEN 1 AND 160),
                    quantity INTEGER NOT NULL CHECK(quantity > 0),
                    created_at TEXT NOT NULL
                )"""
            )

    def get_grocery_list(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT id, name, quantity, created_at FROM grocery_list_items ORDER BY created_at, id"
            ).fetchall()
        return [dict(row) for row in rows]

    def add_grocery_list_item(self, name: str, quantity: int) -> dict[str, Any]:
        item = {
            "id": str(uuid.uuid4()),
            "name": name,
            "quantity": quantity,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO grocery_list_items (id, name, quantity, created_at) VALUES (?, ?, ?, ?)",
                (item["id"], item["name"], item["quantity"], item["created_at"]),
            )
        return item

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(str(self.path))
        connection.row_factory = sqlite3.Row
        return connection
