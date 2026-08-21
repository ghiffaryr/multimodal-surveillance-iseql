from __future__ import annotations

from typing import Optional

from fastapi import HTTPException, Query

from service.events_service import EventSpec
from service.impl.event_registry_service_impl import EventRegistryServiceImpl, _registry_conn


_DELTA_FIELDS = (
    "delta_visual", "delta_audio", "epsilon_visual", "epsilon_audio",
    "eta_visual", "eta_audio", "zeta_visual", "zeta_audio", "rho_visual", "rho_audio",
)


def _derived_delta_fields(model_json: str | None) -> dict[str, str | None]:
    from service.impl.events_service_impl import derive_delta_fields
    delta = derive_delta_fields(model_json) if model_json else {}
    return {f: delta.get(f) for f in _DELTA_FIELDS}


def _spec_dict(spec: EventSpec) -> dict:
    return {
        "id": spec.id,
        "condition": spec.condition,
        **_derived_delta_fields(spec.model_json),
        "model_json": spec.model_json,
    }


class EventRegistryController:
    def __init__(self, service: EventRegistryServiceImpl | None = None) -> None:
        self._service = service or EventRegistryServiceImpl()

    async def on_get(self, condition: Optional[str] = Query(None)) -> dict:
        conn = _registry_conn()
        try:
            if condition is not None:
                specs = self._service.list_events(conn, condition=condition)
            else:
                specs = self._service.list_events(conn)
        finally:
            conn.close()
        return {"events": [_spec_dict(s) for s in specs]}

    async def on_post(self, payload: dict) -> dict:
        spec = _event_spec_from_payload(payload)
        conn = _registry_conn()
        try:
            created = self._service.create_event(conn, spec)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        finally:
            conn.close()
        return _spec_dict(created)


class EventRegistryItemController:
    def __init__(self, service: EventRegistryServiceImpl | None = None) -> None:
        self._service = service or EventRegistryServiceImpl()

    async def on_get(self, event_id: str, condition: str = Query(...)) -> dict:
        conn = _registry_conn()
        try:
            spec = self._service.get_event(conn, event_id, condition)
        finally:
            conn.close()
        if spec is None:
            raise HTTPException(status_code=404, detail=f"event '{event_id}' not found for condition {condition}")
        return _spec_dict(spec)

    async def on_put(self, event_id: str, payload: dict) -> dict:
        condition = payload.get("condition")
        if not condition:
            raise HTTPException(status_code=400, detail="'condition' is required")
        fields = {k: v for k, v in payload.items() if k != "condition"}
        if "model_json" in fields:
            import json as _json
            model = fields["model_json"]
            if isinstance(model, (dict, list)):
                model = _json.dumps(model)
            fields["model_json"] = model
        conn = _registry_conn()
        try:
            updated = self._service.update_event(conn, event_id, condition, fields)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        finally:
            conn.close()
        if updated is None:
            raise HTTPException(status_code=404, detail=f"event '{event_id}' not found for condition {condition}")
        return _spec_dict(updated)

    async def on_delete(self, event_id: str, condition: str = Query(...)) -> dict:
        conn = _registry_conn()
        try:
            self._service.delete_event(conn, event_id, condition)
        finally:
            conn.close()
        return {"status": "deleted", "id": event_id, "condition": condition}

    async def on_patch(self, event_id: str, payload: dict) -> dict:
        condition = payload.get("condition")
        if not condition:
            raise HTTPException(status_code=400, detail="'condition' is required")
        conn = _registry_conn()
        try:
            fields = {k: v for k, v in payload.items() if k != "condition"}
            updated = self._service.update_event(conn, event_id, condition, fields)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        finally:
            conn.close()
        if updated is None:
            raise HTTPException(status_code=404, detail=f"event '{event_id}' not found for condition {condition}")
        return _spec_dict(updated)


def _event_spec_from_payload(payload: dict) -> EventSpec:
    import json as _json
    missing = [k for k in ("id", "condition") if k not in payload]
    if missing:
        raise ValueError(f"missing required field(s): {', '.join(missing)}")
    model = payload.get("model_json")
    if isinstance(model, (dict, list)):
        model = _json.dumps(model)
    return EventSpec(
        id=payload["id"],
        condition=payload["condition"],
        model_json=model,
    )
