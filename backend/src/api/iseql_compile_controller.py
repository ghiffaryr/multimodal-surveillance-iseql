from __future__ import annotations

from fastapi import HTTPException

from iseql import compile_query


class IseqlCompileController:
    """Compile an ISEQL query written as text into SQL (event editor)."""

    async def on_post(self, payload: dict) -> dict:
        query = payload.get("query")
        if not isinstance(query, str) or not query.strip():
            raise HTTPException(status_code=400, detail="'query' is required")
        name = str(payload.get("name") or "event")
        delta_unit = payload.get("delta_unit") or "seconds"
        if delta_unit not in ("seconds", "frames"):
            raise HTTPException(status_code=400, detail="'delta_unit' must be 'seconds' or 'frames'")
        condition = payload.get("condition")
        if condition is not None and condition not in ("A", "B", "C"):
            raise HTTPException(status_code=400, detail="'condition' must be 'A', 'B' or 'C'")
        try:
            return compile_query(query, name=name, delta_unit=delta_unit, condition=condition)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"invalid ISEQL query: {e}")
