from __future__ import annotations

from fastapi import HTTPException

from iseql import render_model


class IseqlPreviewController:
    """Render an event model to ISEQL text (editor prefill)."""

    async def on_post(self, payload: dict) -> dict:
        model = payload.get("model")
        if model is None:
            raise HTTPException(status_code=400, detail="'model' is required")
        try:
            return {"iseql": render_model(model)}
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"invalid model: {e}")
