from __future__ import annotations

import json
import sqlite3
from typing import Optional

from service.events_service import EventSpec
from service.event_registry_service import EventRegistryService

_EVENT_SPEC_COLUMNS = ("id", "condition", "model_json")


def _row_to_spec(row) -> EventSpec:
    return EventSpec(
        id=row["id"],
        condition=row["condition"],
        model_json=row["model_json"],
    )


def _spec_to_row(spec: EventSpec) -> tuple:
    return (spec.id, spec.condition, spec.model_json)


class EventRegistryServiceImpl(EventRegistryService):
    def list_events(
        self,
        conn: sqlite3.Connection,
        condition: Optional[str] = None,
    ) -> list[EventSpec]:
        where = []
        params: list = []
        if condition is not None:
            where.append("condition = ?")
            params.append(condition)
        clause = ("WHERE " + " AND ".join(where)) if where else ""
        rows = conn.execute(
            f"SELECT {','.join(_EVENT_SPEC_COLUMNS)} FROM EventSpec {clause} ORDER BY condition, id",
            params,
        ).fetchall()
        return [_row_to_spec(r) for r in rows]

    def get_event(
        self, conn: sqlite3.Connection, event_id: str, condition: str
    ) -> Optional[EventSpec]:
        row = conn.execute(
            f"SELECT {','.join(_EVENT_SPEC_COLUMNS)} FROM EventSpec WHERE id=? AND condition=?",
            (event_id, condition),
        ).fetchone()
        return _row_to_spec(row) if row else None

    def create_event(self, conn: sqlite3.Connection, spec: EventSpec) -> EventSpec:
        if self.get_event(conn, spec.id, spec.condition) is not None:
            raise ValueError(f"event '{spec.id}' already exists for condition {spec.condition}")
        placeholders = ",".join("?" * len(_EVENT_SPEC_COLUMNS))
        conn.execute(
            f"INSERT INTO EventSpec ({','.join(_EVENT_SPEC_COLUMNS)}) VALUES ({placeholders})",
            _spec_to_row(spec),
        )
        conn.commit()
        return self.get_event(conn, spec.id, spec.condition)

    def update_event(
        self, conn: sqlite3.Connection, event_id: str, condition: str, fields: dict
    ) -> EventSpec:
        allowed = {"model_json"}
        unknown = set(fields) - allowed
        if unknown:
            raise ValueError(f"unknown event field(s): {sorted(unknown)}")
        assignments = ", ".join(f"{k} = ?" for k in fields)
        params = list(fields.values()) + [event_id, condition]
        conn.execute(
            f"UPDATE EventSpec SET {assignments}, updated_at = datetime('now') "
            "WHERE id = ? AND condition = ?",
            params,
        )
        conn.commit()
        return self.get_event(conn, event_id, condition)

    def delete_event(
        self, conn: sqlite3.Connection, event_id: str, condition: str
    ) -> None:
        conn.execute(
            "DELETE FROM EventSpec WHERE id = ? AND condition = ?",
            (event_id, condition),
        )
        conn.commit()

    def required_deltas(self, conn: sqlite3.Connection, condition: str) -> set[str]:
        specs = self.list_events(conn, condition=condition)
        required: set[str] = set()
        for e in specs:
            if not e.model_json:
                continue
            try:
                model = json.loads(e.model_json)
            except (TypeError, ValueError):
                continue
            for entry in (model.get("delta_map") or {}).values():
                if not isinstance(entry, dict):
                    continue
                for key in ("delta", "epsilon", "eta", "zeta", "rho"):
                    val = entry.get(key)
                    if isinstance(val, str):
                        required.add(val)
        return required


def _registry_conn() -> sqlite3.Connection:
    from utils.config import Config
    conn = sqlite3.connect(str(Config.get().data.db_path), timeout=30.0)
    conn.row_factory = sqlite3.Row
    return conn
