from __future__ import annotations

from fastapi import APIRouter

from __init__ import __app_name__, __version__
from utils.config import Config

from service.impl.events_service_impl import events_for_condition

def _event_specs(condition: str) -> list[tuple]:
    return [
        (e.id, e.label, e.delta_param, e.condition, e.requires_cpp, e.delta_param2)
        for e in events_for_condition(condition)
    ]

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
                "SoundPerInterval": "SoundIntervalID PK, StartFrame, EndFrame, SoundClass, Confidence",

            },
            "events": {
                "A_visual": [e[0] for e in _event_specs("A")],
                "B_sound_only": [e[0] for e in _event_specs("B")],
                "C_sound_visual": [e[0] for e in _event_specs("C")],
            },
        }

class EventTypesController:
    async def on_get(self) -> dict:
        return {
            "A_visual": [
                {"id": e[0], "label": e[1], "delta_param": e[2], "condition": e[3], "requires_cpp": e[4], "delta_param2": e[5]}
                for e in _event_specs("A")
            ],
            "B_sound_only": [
                {"id": e[0], "label": e[1], "delta_param": e[2], "condition": e[3], "requires_cpp": e[4], "delta_param2": e[5]}
                for e in _event_specs("B")
            ],
            "C_sound_visual": [
                {"id": e[0], "label": e[1], "delta_param": e[2], "condition": e[3], "requires_cpp": e[4], "delta_param2": e[5]}
                for e in _event_specs("C")
            ],
        }
