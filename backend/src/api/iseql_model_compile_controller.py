from __future__ import annotations

from fastapi import HTTPException

from iseql import compile_model


class IseqlModelCompileController:
    """Compile an event model (groups + set-expression tree) directly to SQL."""

    async def on_post(self, payload: dict) -> dict:
        model = payload.get("model")
        if model is None:
            raise HTTPException(status_code=400, detail="'model' is required")
        condition = payload.get("condition")
        if condition is not None and condition not in ("A", "B", "C"):
            raise HTTPException(status_code=400, detail="'condition' must be 'A', 'B' or 'C'")
        try:
            return compile_model(model, condition=condition)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"invalid model: {e}")
