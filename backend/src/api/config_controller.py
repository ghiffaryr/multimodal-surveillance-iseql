from __future__ import annotations

from fastapi import HTTPException

from service.impl.config_store_service_impl import KNOWN_SECTIONS, ConfigStoreServiceImpl, _config_conn


class ConfigController:
    def __init__(self, service: ConfigStoreServiceImpl | None = None) -> None:
        self._service = service or ConfigStoreServiceImpl()

    async def on_get(self) -> dict:
        conn = _config_conn()
        try:
            sections = self._service.list_sections(conn)
        finally:
            conn.close()
        return {"sections": sections}

    async def on_put(self, key: str, payload: dict) -> dict:
        if key not in KNOWN_SECTIONS:
            raise HTTPException(status_code=400, detail=f"unknown config section '{key}'; expected one of {sorted(KNOWN_SECTIONS)}")
        conn = _config_conn()
        try:
            self._service.set_section(conn, key, payload)
            saved = self._service.get_section(conn, key)
        finally:
            conn.close()
        return {"key": key, "value": saved}

    async def on_delete(self, key: str) -> dict:
        if key not in KNOWN_SECTIONS:
            raise HTTPException(status_code=400, detail=f"unknown config section '{key}'")
        conn = _config_conn()
        try:
            self._service.delete_section(conn, key)
        finally:
            conn.close()
        return {"status": "deleted", "key": key}
