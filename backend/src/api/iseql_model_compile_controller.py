from __future__ import annotations

from fastapi import HTTPException

from iseql import compile_model


class IseqlModelCompileController:
    """Compile an event model (groups + set-expression tree) directly to SQL."""

    async def on_post(self, payload: dict) -> dict:
        model = payload.get("model")
        if model is None:
            raise HTTPException(status_code=400, detail="'model' is required")
        try:
            return compile_model(model)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"invalid model: {e}")
