"""SQLite storage for the household grocery list (single-household demo)."""

from __future__ import annotations

import os
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.settings import REPOSITORY_ROOT

MAX_NAME_LENGTH = 160
DEFAULT_PATH = REPOSITORY_ROOT / "data" / "homepilot.sqlite3"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS grocery_list_items (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL CHECK (length(trim(name)) BETWEEN 1 AND 160),
    quantity INTEGER NOT NULL CHECK (typeof(quantity) = 'integer' AND quantity > 0),
    created_at TEXT NOT NULL
)
"""


def clean_item(name: Any, quantity: Any) -> tuple[str, int]:
    """Return a trimmed name and quantity, or raise ValueError for anything unsafe to store."""
    if not isinstance(name, str) or not name.strip():
        raise ValueError("name must not be blank")
    if len(name.strip()) > MAX_NAME_LENGTH:
        raise ValueError(f"name must be at most {MAX_NAME_LENGTH} characters")
    if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity < 1:
        raise ValueError("quantity must be a positive whole number")
    return name.strip(), quantity


class GroceryListRepository:
    """Reads and writes grocery-list rows. Every call opens and closes its own connection."""

    def __init__(self, path: str | Path | None = None) -> None:
        chosen = path or os.getenv("HOME_PILOT_DATABASE_PATH") or DEFAULT_PATH
        self.path = Path(chosen).expanduser()

    def _connection(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        return connection

    def create_schema(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connection()) as connection, connection:
            connection.execute(_SCHEMA)

    def list_items(self) -> list[dict[str, Any]]:
        with closing(self._connection()) as connection:
            rows = connection.execute(
                "SELECT id, name, quantity, created_at FROM grocery_list_items ORDER BY created_at, id"
            )
            return [dict(row) for row in rows]

    def add_item(self, name: Any, quantity: Any) -> dict[str, Any]:
        clean_name, clean_quantity = clean_item(name, quantity)
        row = {
            "id": str(uuid4()),
            "name": clean_name,
            "quantity": clean_quantity,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        with closing(self._connection()) as connection, connection:
            connection.execute(
                "INSERT INTO grocery_list_items (id, name, quantity, created_at) "
                "VALUES (:id, :name, :quantity, :created_at)",
                row,
            )
        return row
