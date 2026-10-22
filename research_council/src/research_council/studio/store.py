"""Durable application records, kept separate from canonical scientific state."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


class StudioStore:
    def __init__(self, workspace: Path) -> None:
        self.path = workspace / "studio.db"
        with sqlite3.connect(self.path) as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute(
                "CREATE TABLE IF NOT EXISTS records "
                "(kind TEXT, id TEXT, payload TEXT NOT NULL, PRIMARY KEY(kind,id))"
            )

    def put(self, kind: str, identity: str, value: dict[str, Any]) -> dict[str, Any]:
        with sqlite3.connect(self.path) as db:
            db.execute(
                "INSERT INTO records VALUES (?,?,?) ON CONFLICT(kind,id) "
                "DO UPDATE SET payload=excluded.payload",
                (kind, identity, json.dumps(value, ensure_ascii=False)),
            )
        return value

    def get(self, kind: str, identity: str) -> dict[str, Any]:
        with sqlite3.connect(self.path) as db:
            row = db.execute(
                "SELECT payload FROM records WHERE kind=? AND id=?", (kind, identity)
            ).fetchone()
        if not row:
            raise KeyError("Unknown Studio record")
        return dict(json.loads(row[0]))

    def list(self, kind: str) -> list[dict[str, Any]]:
        with sqlite3.connect(self.path) as db:
            rows = db.execute("SELECT payload FROM records WHERE kind=? ORDER BY rowid", (kind,))
            return [dict(json.loads(row[0])) for row in rows]
