from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException

from utils.config import Config
from utils.object_memory import ObjectMemory


def _memory() -> ObjectMemory:
    memory_dir = Path(Config.get().data.dir) / "vector_db"
    return ObjectMemory(memory_dir)


class ObjectMemoryStatsController:
    """Read-only summary of the Chroma object-memory store for an analysis."""

    async def on_get(self, analysis_id: str) -> dict:
        try:
            return _memory().stats(analysis_id)
        except Exception as e:
            raise HTTPException(status_code=404,
                                detail=f"object memory not available for '{analysis_id}': {e}")


class ObjectMemoryObjectsController:
    """Read-only paginated listing of the object-memory entries for an analysis."""

    async def on_get(self, analysis_id: str, limit: int = 200, offset: int = 0,
                     class_name: str | None = None, frame_min: int | None = None,
                     frame_max: int | None = None) -> dict:
        try:
            return _memory().list_entries(
                analysis_id,
                class_name=class_name,
                frame_min=frame_min,
                frame_max=frame_max,
                limit=min(max(limit, 1), 1000),
                offset=max(offset, 0),
            )
        except Exception as e:
            raise HTTPException(status_code=404,
                                detail=f"object memory not available for '{analysis_id}': {e}")