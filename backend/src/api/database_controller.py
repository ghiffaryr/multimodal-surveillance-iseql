from __future__ import annotations

import shutil
import sqlite3
import tempfile
from pathlib import Path

from fastapi import File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from utils.config import Config
from utils.api_logger import get_logger

log = get_logger(__name__)

class DatabaseUploadController:
    async def on_post(self, database_file: UploadFile = File(...)) -> dict:
        cfg = Config.get()
        db_path = Path(cfg.data.db_path)
        if not database_file.filename or not database_file.filename.endswith(".db"):
            raise HTTPException(status_code=400, detail="please upload a .db file")

        db_path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=".db", dir=str(db_path.parent)
        ) as tmp:
            shutil.copyfileobj(database_file.file, tmp)
            tmp_path = Path(tmp.name)
        try:
            with sqlite3.connect(str(tmp_path)) as conn:
                conn.execute("SELECT name FROM sqlite_master LIMIT 1").fetchone()
            shutil.move(str(tmp_path), str(db_path))
            log.info("Database uploaded to %s", db_path)
            return {"success": True, "filename": database_file.filename, "path": str(db_path)}
        except Exception as e:
            tmp_path.unlink(missing_ok=True)
            raise HTTPException(status_code=400, detail=f"uploaded file is not a valid SQLite database: {e}")

class DatabaseDownloadController:
    async def on_get(self) -> FileResponse:
        cfg = Config.get()
        db_path = Path(cfg.data.db_path)
        if not db_path.exists():
            raise HTTPException(status_code=404, detail="database does not exist yet")
        return FileResponse(
            path=str(db_path),
            filename="analysis.db",
            media_type="application/octet-stream",
        )


class DatabaseResetController:
    def __init__(self, analysis_service) -> None:
        self._service = analysis_service

    async def on_post(self) -> dict:
        self._service.reset_database()
        return {"status": "reset"}
