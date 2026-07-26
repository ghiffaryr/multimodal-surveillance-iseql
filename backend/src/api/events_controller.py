from __future__ import annotations

class EventsDetectController:
    async def on_post(self, payload: dict) -> dict:
        return {"event_type": payload.get("event_type"), "results": []}
