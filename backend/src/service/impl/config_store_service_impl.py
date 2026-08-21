from __future__ import annotations

import json
import sqlite3
from typing import Optional

from service.config_store_service import ConfigStoreService

KNOWN_SECTIONS = ("audio_taxonomy", "relation_vocab")


class ConfigStoreServiceImpl(ConfigStoreService):
    def get_section(self, conn: sqlite3.Connection, key: str) -> Optional[dict]:
        row = conn.execute(
            "SELECT value_json FROM AppConfig WHERE key = ?", (key,)
        ).fetchone()
        if row is None:
            return None
        try:
            value = json.loads(row["value_json"])
        except (json.JSONDecodeError, TypeError):
            return None
        return value if isinstance(value, dict) else None

    def set_section(self, conn: sqlite3.Connection, key: str, value: dict) -> None:
        if not isinstance(value, dict):
            raise ValueError(f"config section '{key}' must be a JSON object")
        conn.execute(
            "INSERT INTO AppConfig (key, value_json, updated_at) VALUES (?, ?, datetime('now')) "
            "ON CONFLICT(key) DO UPDATE SET value_json = excluded.value_json, updated_at = datetime('now')",
            (key, json.dumps(value)),
        )
        conn.commit()

    def list_sections(self, conn: sqlite3.Connection) -> dict[str, dict]:
        rows = conn.execute("SELECT key, value_json FROM AppConfig").fetchall()
        out: dict[str, dict] = {}
        for r in rows:
            try:
                value = json.loads(r["value_json"])
            except (json.JSONDecodeError, TypeError):
                continue
            if isinstance(value, dict):
                out[r["key"]] = value
        return out

    def delete_section(self, conn: sqlite3.Connection, key: str) -> None:
        conn.execute("DELETE FROM AppConfig WHERE key = ?", (key,))
        conn.commit()


def _config_conn() -> sqlite3.Connection:
    from utils.config import Config
    conn = sqlite3.connect(str(Config.get().data.db_path), timeout=30.0)
    conn.row_factory = sqlite3.Row
    return conn
