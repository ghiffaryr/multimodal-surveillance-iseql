from __future__ import annotations

import asyncio
import datetime
import json
import shutil
import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import AsyncIterator, Dict, List, Optional

from fastapi import File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from __init__ import __app_name__
from utils.config import VALID_CONDITIONS, Config
from utils.api_logger import get_logger
from utils.database import setup_database
from utils.vlm_client import VLMClient, DEFAULT_MODELS, ENV_KEYS
from models.analysis import (
    AnalysisStage,
    AnalysisStartResponse,
    AnalysisStatusResponse,
    Condition,
)

log = get_logger(__name__)
@dataclass
class RunState:
    id: str
    video_path: Path
    video_filename: str
    condition: str
    vlm_provider: str
    model: str
    grid_rows: int
    grid_cols: int
    sampling_rate: int
    vlm_delay: float = 0.0
    vlm_quantization: str = "none"
    max_retries: int = 3
    audio_provider: str = "panns"
    audio_model: str = "cnn14"
    audio_quantization: str = "none"
    stage: AnalysisStage = AnalysisStage.QUEUED
    counters: Dict[str, int] = field(default_factory=dict)
    log_queue: "asyncio.Queue[dict]" = field(default_factory=asyncio.Queue)
    done: bool = False
    error: Optional[str] = None

_RUNS: Dict[str, RunState] = {}

def _get_run(analysis_id: str) -> RunState:
    run = _RUNS.get(analysis_id)
    if run:
        return run
    cfg = Config.get()
    try:
        conn = sqlite3.connect(str(cfg.data.db_path), timeout=60.0)
        conn.row_factory = sqlite3.Row
        row = conn.execute("""
            SELECT ID, VideoPath, VideoFilename, Condition, VLMProvider, Model,
                   GridRows, GridCols, SamplingRate, VLMDelay,
                   VLMQuantization, MaxRetries, AudioProvider, AudioModel, AudioQuantization, Stage
            FROM Analyses WHERE ID = ?
        """, (analysis_id,)).fetchone()
        conn.close()
        if row:
            run = RunState(
                id=row["ID"],
                video_path=Path(row["VideoPath"]),
                video_filename=row["VideoFilename"],
                condition=row["Condition"],
                vlm_provider=row["VLMProvider"] or "ollama",
                model=row["Model"] or "",
                grid_rows=row["GridRows"] or 2,
                grid_cols=row["GridCols"] or 4,
                sampling_rate=row["SamplingRate"] or 24,
                vlm_delay=row["VLMDelay"] or 0.0,
                vlm_quantization=row["VLMQuantization"] or "none",
                max_retries=row["MaxRetries"] or 3,
                audio_provider=row["AudioProvider"] or "",
                audio_model=row["AudioModel"] or "",
                audio_quantization=row["AudioQuantization"] or "",
                stage=AnalysisStage(row["Stage"]) if row["Stage"] else AnalysisStage.QUEUED,
            )
            _RUNS[analysis_id] = run
            return run
    except Exception:
        pass
    raise HTTPException(status_code=404, detail=f"unknown analysis_id '{analysis_id}'")

def load_runs_from_db() -> int:
    """Load the most recent run from database into memory on server startup."""
    cfg = Config.get()
    db_path = Path(cfg.data.db_path)
    if not db_path.exists():
        return 0
    
    try:
        conn = sqlite3.connect(str(db_path), timeout=60.0)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT ID, VideoPath, VideoFilename, Condition, VLMProvider, Model, "
            "GridRows, GridCols, SamplingRate, VLMDelay, "
            "VLMQuantization, MaxRetries, AudioProvider, AudioModel, AudioQuantization, Stage "
            "FROM Analyses ORDER BY CreatedAt DESC LIMIT 1"
        ).fetchone()
        conn.close()
        
        if not row or row["ID"] in _RUNS:
            return 0
        
        try:
            run = RunState(
                id=row["ID"],
                video_path=Path(row["VideoPath"]),
                video_filename=row["VideoFilename"],
                condition=row["Condition"],
                vlm_provider=row["VLMProvider"] or "ollama",
                model=row["Model"] or "",
                grid_rows=row["GridRows"] or 2,
                grid_cols=row["GridCols"] or 4,
                sampling_rate=row["SamplingRate"] or 24,
                vlm_delay=row["VLMDelay"] or 0.0,
                vlm_quantization=row["VLMQuantization"] or "none",
                max_retries=row["MaxRetries"] or 3,
                audio_provider=row["AudioProvider"] or "panns",
                audio_model=row["AudioModel"] or "cnn14",
                audio_quantization=row["AudioQuantization"] or "none",
                stage=AnalysisStage(row["Stage"]),
            )
            _RUNS[row["ID"]] = run
            log.info("Restored previous analysis run: %s", row["ID"])
            return 1
        except Exception as e:
            log.warning("Failed to restore run %s: %s", row["ID"], e)
            return 0
    except Exception as e:
        log.warning("Failed to load run from database: %s", e)
        return 0

async def _emit(run: RunState, stage: str, message: str, **extra) -> None:
    payload = {"ts": time.time(), "stage": stage, "message": message, **extra}
    await run.log_queue.put(payload)

def _sse_format(event: str, data: str) -> str:
    lines = ["event: " + event]
    for chunk_line in data.split("\n"):
        lines.append("data: " + chunk_line)
    lines.append("")
    return "\n".join(lines) + "\n"

async def _drain_queue_into_sse(run: RunState) -> AsyncIterator[str]:
    while True:
        item = await run.log_queue.get()
        yield _sse_format("log", json.dumps(item))
        if item.get("message") == "<<RUN_DONE>>":
            yield _sse_format("end", "{}")
            return
        if item.get("message") == "<<RUN_FAILED>>":
            yield _sse_format("end", "{}")
            return

def _run_analysis_worker(run: RunState) -> None:
    cfg = Config.get()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    _stage_conn: sqlite3.Connection = None

    def _persist_stage(stage: str) -> None:
        nonlocal _stage_conn
        try:
            if _stage_conn is None:
                _stage_conn = sqlite3.connect(str(cfg.data.db_path), timeout=60.0)
            _stage_conn.execute(
                "UPDATE Analyses SET Stage = ? WHERE ID = ?",
                (stage, run.id),
            )
            _stage_conn.commit()
        except Exception as e:
            log.warning("Failed to persist stage for %s: %s", run.id, e)

    async def push(stage: str, msg: str) -> None:
        await _emit(run, stage, msg)

    def _log(msg: str) -> None:
        try:
            loop.run_until_complete(push(run.stage.value, msg))
        except RuntimeError:
            asyncio.run_coroutine_threadsafe(push(run.stage.value, msg), loop)

    try:
        conn, _cursor = setup_database(Path(cfg.data.db_path))

        if run.condition in ("A", "C"):
            from service.impl.visual_service_impl import VisualServiceImpl
            from service.impl.interval_service_impl import IntervalServiceImpl

            run.stage = AnalysisStage.VLM
            _persist_stage("vlm")
            _log(f">>> CONDITION {run.condition}: visual perception (VLM)")
            _log(f"     Provider: {run.vlm_provider}, Model: {run.model or '(default)'}, "
                f"Grid: {run.grid_rows}x{run.grid_cols}, Sampling: every {run.sampling_rate} frames"
                f", Delay: {run.vlm_delay}s")
            
            try:
                client = VLMClient(
                    provider=run.vlm_provider,
                    model=run.model or None,
                    base_url=cfg.vlm.ollama_base_url if run.vlm_provider == "ollama" else None
                )
                visual = VisualServiceImpl(max_retries=run.max_retries)
                visual.run_pipeline(
                    video_path=str(run.video_path),
                    conn=conn,
                    client=client,
                    grid_rows=run.grid_rows,
                    grid_cols=run.grid_cols,
                    sampling_rate=run.sampling_rate,
                    min_interval=run.vlm_delay,
                    analysis_id=run.id,
                    log=_log,
                )
            except Exception as e:
                import traceback
                _log(f"VLM pipeline error: {e}")
                log.info("VLM pipeline error [%s]: %s\n%s", run.id, e, traceback.format_exc())
                raise

            run.stage = AnalysisStage.INTERVAL
            _persist_stage("interval")
            _log(">>> PHASE 2 START: interval construction (inside VLM pipeline)")
        else:
            _log(">>> CONDITION B: skipping VLM (sound-only condition)")

        if run.condition in ("B", "C"):
            from service.impl.audio_service_impl import AudioServiceImpl
            run.stage = AnalysisStage.SOUND
            _persist_stage("sound")
            _log(f">>> CONDITION {run.condition}: sound perception ({run.audio_provider})")
            try:
                out_dir = Path(cfg.data.dir) / "audio"
                out_dir.mkdir(parents=True, exist_ok=True)
                audio = AudioServiceImpl(
                    audio_provider=run.audio_provider,
                    audio_model=run.audio_model or None,
                    quantization=run.audio_quantization,
                )
                result = audio.run_pipeline(
                    video_path=run.video_path,
                    conn=conn,
                    out_dir=out_dir,
                    fps=run.sampling_rate,
                    analysis_id=run.id,
                    log_fn=_log,
                )
                _log(f"     {result['n_sound_events']} per-frame rows persisted")
            except Exception as e:
                _log(f"sound pipeline error: {e}")
                if run.condition == "B":
                    raise

        else:
            _log(">>> CONDITION A: skipping sound pipeline (visual-only condition)")

        conn.close()
        run.stage = AnalysisStage.DONE
        _persist_stage("done")
        try:
            if _stage_conn is not None:
                _stage_conn.execute(
                    "UPDATE Analyses SET CompletedAt = ? WHERE ID = ?",
                    (datetime.datetime.now().isoformat(), run.id),
                )
                _stage_conn.commit()
        except Exception as e:
            log.warning("Failed to persist completion time: %s", e)
        _log(">>> ANALYSIS COMPLETE")
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        _log(f"CRITICAL ERROR: {e}")
        log.info("CRITICAL ERROR [%s]: %s\n%s", run.id, e, tb)
        run.stage = AnalysisStage.FAILED
        run.error = f"{e}\n{tb}"
    finally:
        if _stage_conn is not None:
            _stage_conn.close()
        loop.run_until_complete(_emit(run, run.stage.value, "<<RUN_DONE>>"))
        loop.close()

class AnalysisStartController:
    async def on_post(
        self,
        video: UploadFile = File(...),
        condition: str = Form("A"),
        vlm_provider: str = Form(None),
        model: str = Form(""),
        grid_rows: int = Form(2),
        grid_cols: int = Form(4),
        sampling_rate: int = Form(24),
        vlm_delay: float = Form(0.0),
    vlm_quantization: str = Form("none"),
    max_retries: int = Form(3),
    audio_provider: str = Form("panns"),
        audio_model: str = Form("cnn14"),
        audio_quantization: str = Form("none"),
    ) -> AnalysisStartResponse:
        cfg = Config.get()
        available_providers = Config.get_available_providers()
        
        if condition not in VALID_CONDITIONS:
            raise HTTPException(
                status_code=400,
                detail=f"unknown condition '{condition}'; expected A | B | C",
            )
        
        if vlm_provider is None:
            vlm_provider = available_providers[0] if available_providers else "ollama"
        
        if condition in ("A", "C") and vlm_provider not in available_providers:
            raise HTTPException(
                status_code=400,
                detail=f"Provider '{vlm_provider}' not available. Available providers: {available_providers}"
            )

        upload_dir = Path(cfg.data.upload_dir)
        upload_dir.mkdir(parents=True, exist_ok=True)
        analysis_id = uuid.uuid4().hex[:12]
        safe_name = Path(video.filename or "upload.mp4").name
        target_path = upload_dir / f"{analysis_id}_{safe_name}"
        with target_path.open("wb") as f:
            shutil.copyfileobj(video.file, f)
        log.info("Stored upload as %s (condition=%s)", target_path, condition)

        run = RunState(
            id=analysis_id,
            video_path=target_path,
            video_filename=safe_name,
            condition=condition,
            vlm_provider=vlm_provider,
            model=model,
            grid_rows=grid_rows,
            grid_cols=grid_cols,
            sampling_rate=sampling_rate,
            vlm_delay=vlm_delay,
            vlm_quantization=vlm_quantization,
            max_retries=max_retries,
            audio_provider=audio_provider,
            audio_model=audio_model,
            audio_quantization=audio_quantization,
        )
        _RUNS[analysis_id] = run

        try:
            conn = sqlite3.connect(str(cfg.data.db_path), timeout=60.0)
            from utils.database import setup_database
            setup_database(Path(cfg.data.db_path))
            conn.execute(
                "INSERT INTO Analyses (ID, VideoPath, VideoFilename, Condition, VLMProvider, Model, GridRows, GridCols, SamplingRate, VLMDelay, VLMQuantization, MaxRetries, AudioProvider, AudioModel, AudioQuantization, Stage, CreatedAt) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (analysis_id, str(target_path), safe_name, condition, vlm_provider, model, grid_rows, grid_cols, sampling_rate, vlm_delay, vlm_quantization, max_retries, audio_provider, audio_model, audio_quantization, "queued", datetime.datetime.now().isoformat()),
            )
            conn.commit()
            conn.close()
        except Exception as e:
            log.warning("Failed to persist analysis metadata: %s", e)

        asyncio.get_event_loop().run_in_executor(None, _run_analysis_worker, run)

        return AnalysisStartResponse(
            analysis_id=analysis_id,
            condition=Condition(condition),
            stage=AnalysisStage.QUEUED,
        )

class AnalysisLogsController:
    async def on_get(self, analysis_id: str) -> StreamingResponse:
        run = _get_run(analysis_id)
        return StreamingResponse(
            _drain_queue_into_sse(run),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

class AnalysisStatusController:
    async def on_get(self, analysis_id: str) -> dict:
        run = _get_run(analysis_id)
        return {
            "id": run.id,
            "condition": run.condition,
            "stage": run.stage.value if hasattr(run.stage, "value") else str(run.stage),
            "counters": run.counters,
            "error": getattr(run, "error", None),
        }

class AnalysisListController:
    async def on_get(self) -> list[dict]:
        cfg = Config.get()
        try:
            conn = sqlite3.connect(str(cfg.data.db_path), timeout=60.0)
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT ID, VideoFilename, Condition, VLMProvider, Model, Stage, CreatedAt, CompletedAt FROM Analyses ORDER BY CreatedAt DESC"
            ).fetchall()
            conn.close()
            return [
                {
                    "id": row["ID"],
                    "video_filename": row["VideoFilename"],
                    "condition": row["Condition"],
                    "vlm_provider": row["VLMProvider"],
                    "model": row["Model"],
                    "stage": row["Stage"],
                    "created_at": row["CreatedAt"],
                    "completed_at": row["CompletedAt"],
                }
                for row in rows
            ]
        except Exception as e:
            log.warning("Failed to list Analyses: %s", e)
            return []

class AnalysisDetectController:
    async def on_get(
        self,
        analysis_id: str,
        event_type: str,
    ) -> StreamingResponse:
        raise HTTPException(
            status_code=400,
            detail="GET /detect is deprecated. Use POST /detect for SQL-based detection.",
        )

    async def on_post(
        self,
        analysis_id: str,
        event_type: str,
    ) -> dict:
        cfg = Config.get()
        run = _get_run(analysis_id)

        if run.stage != AnalysisStage.DONE:
            raise HTTPException(
                status_code=409,
                detail=f"analysis {analysis_id} is not done (current stage: {run.stage.value})",
            )

        default_deltas: Dict[str, int] = {
            "delta_visual_vehicle_escape": 50,
            "delta_visual_loitering": 150,
            "delta_visual_handoff": 240,
            "delta_visual_fight": 60,
            "delta_sound_fight": 120,
            "delta_sound_gunshot_or_explosion": 60,
            "delta_sound_vehicle_escape": 150,
            "delta_sound_loitering": 30,
            "delta_sound_vehicle_collision": 60,
        }
        deltas = dict(default_deltas)

        log.info("Detect request: id=%s cond=%s event=%s deltas=%s",
                 analysis_id, run.condition, event_type, deltas)

        from service.impl.events_service_impl import events_for_condition, run_sql_detection
        valid_ids = {e.id for e in events_for_condition(run.condition)}
        if event_type not in valid_ids:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"event '{event_type}' is not available for condition {run.condition}; "
                    f"valid: {sorted(valid_ids)}"
                ),
            )

        rows: list[dict] = []
        try:
            conn = sqlite3.connect(str(cfg.data.db_path), timeout=60.0)
            try:
                for line in run_sql_detection(conn, event_type, deltas, analysis_id=run.id, condition=run.condition):
                    if line.startswith("__RESULT__:"):
                        payload = line[len("__RESULT__:"):]
                        try:
                            rows = json.loads(payload)
                        except Exception:
                            rows = []
            finally:
                conn.close()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"detection failed: {e}")

        return {
            "analysis_id": analysis_id,
            "event_type": event_type,
            "condition": run.condition,
            "rows": rows,
        }

class VLMModelsController:
    async def on_get(self, provider: str = "ollama") -> dict:
        available_providers = Config.get_available_providers()
        
        if provider not in available_providers:
            raise HTTPException(
                status_code=400, 
                detail=f"Provider '{provider}' not available. Available providers: {available_providers}"
            )

        try:
            client = VLMClient(provider=provider)
            models = client.list_models()
            return {"models": models}
        except Exception as e:
            log.warning("Cannot list models for %s: %s", provider, e)
            return {"models": [], "error": str(e)}
