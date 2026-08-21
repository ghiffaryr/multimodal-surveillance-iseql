from __future__ import annotations

from fastapi import APIRouter

from __init__ import __app_name__, __version__
from utils.config import Config

from service.impl.events_service_impl import default_deltas_for, derive_delta_fields, events_for_condition
from service.impl.event_registry_service_impl import _registry_conn

_DELTA_FIELDS = (
    "delta_visual", "delta_audio", "epsilon_visual", "epsilon_audio",
    "eta_visual", "eta_audio", "zeta_visual", "zeta_audio", "rho_visual", "rho_audio",
)


def _event_specs(condition: str) -> list[dict]:
    conn = _registry_conn()
    try:
        specs = events_for_condition(condition, conn=conn)
    finally:
        conn.close()
    out = []
    for e in specs:
        delta = derive_delta_fields(e.model_json) if e.model_json else {}
        fields = {f: delta.get(f) for f in _DELTA_FIELDS if delta.get(f)}
        out.append({
            "id": e.id,
            **{f: delta.get(f) for f in _DELTA_FIELDS},
            "default_deltas": default_deltas_for(e.model_json, e.id, fields),
            "condition": e.condition,
        })
    return out

class SchemaController:
    async def on_get(self) -> dict:
        return {
            "app": __app_name__,
            "version": __version__,
            "conditions": ["A", "B", "C"],
            "available_providers": Config.get_available_providers(),
            "available_audio_providers": Config.get_available_audio_providers(),
            "tables": {
                "VisualPerFrame": "Frame, ClassID, Class, Block, Description",
                "VisualRelation": "Frame, RelationID, RelationType, ClassID",
                "VisualPerInterval": "RelationID PK, StartFrame, EndFrame, RelationType",
                "VisualParticipant": "RelationID, ClassID, Class",
                "AudioPerInterval": "AudioIntervalID PK, StartFrame, EndFrame, AudioClass, Confidence",

            },
            "events": {
                "A_visual": [e["id"] for e in _event_specs("A")],
                "B_audio_only": [e["id"] for e in _event_specs("B")],
                "C_audio_visual": [e["id"] for e in _event_specs("C")],
            },
        }

class EventTypesController:
    async def on_get(self) -> dict:
        return {
            "A_visual": _event_specs("A"),
            "B_audio_only": _event_specs("B"),
            "C_audio_visual": _event_specs("C"),
        }
