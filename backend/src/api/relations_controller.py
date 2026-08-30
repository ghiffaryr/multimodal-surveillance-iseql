from __future__ import annotations

from fastapi import HTTPException

from service.impl.config_store_service_impl import ConfigStoreServiceImpl, _config_conn
from service.relation_vocab import args_to_classid, classid_to_args


class RelationsController:
    """Relations (visual predicates) in user-facing "args" form.

    The stored ``relation_vocab.relation_classids`` uses ClassID signatures like
    ``(PersonID, VehicleID)``; this controller exposes/accepts the friendly args
    form ``person, vehicle`` and converts at the boundary.
    """

    def __init__(self, service: ConfigStoreServiceImpl | None = None) -> None:
        self._service = service or ConfigStoreServiceImpl()

    async def on_get(self) -> dict:
        conn = _config_conn()
        try:
            vocab = self._service.get_section(conn, "relation_vocab") or {}
        finally:
            conn.close()

        descriptions = vocab.get("relation_descriptions") or {}
        relations = [
            {
                "name": name,
                "args": classid_to_args(str(sig)),
                "description": descriptions.get(name, ""),
            }
            for name, sig in (vocab.get("relation_classids") or [])
        ]
        return {"relations": relations}

    async def on_put(self, payload: dict) -> dict:
        relations = payload.get("relations")
        if not isinstance(relations, list):
            raise HTTPException(status_code=400, detail="'relations' must be a list")

        classids: list[list[str]] = []
        descriptions: dict[str, str] = {}
        for r in relations:
            if not isinstance(r, dict):
                raise HTTPException(status_code=400, detail="each relation must be an object")
            name = str(r.get("name") or "").strip()
            if not name:
                raise HTTPException(status_code=400, detail="relation name is required")
            args = str(r.get("args") or "").strip()
            classids.append([name, args_to_classid(args) or "(ID)"])
            descriptions[name] = str(r.get("description") or "").strip()

        conn = _config_conn()
        try:
            self._service.set_section(conn, "relation_vocab", {
                "relation_classids": classids,
                "relation_descriptions": descriptions,
            })
        finally:
            conn.close()
        return {"status": "saved"}
