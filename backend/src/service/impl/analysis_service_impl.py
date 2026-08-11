from __future__ import annotations

import asyncio
import datetime
import json
import sqlite3
import traceback
import uuid
from pathlib import Path
from typing import Callable

from fastapi import HTTPException

from models.analysis import AnalysisStage, RunState
from service.analysis_service import AnalysisService
from utils.api_logger import get_logger
from utils.config import Config
from utils.database import setup_database
from utils.sse import make_log_entry, SENTINEL_RUN_DONE, SENTINEL_RUN_FAILED

log = get_logger(__name__)

DB_TIMEOUT_SEC = 60.0
ANALYSIS_ID_HEX_LENGTH = 12


def _format_time(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    if h > 0:
        return f"{h}:{m:02d}:{s:05.2f}"
    return f"{m}:{s:05.2f}"


def _get_db_conn(cfg: Config) -> sqlite3.Connection:
    conn = sqlite3.connect(str(cfg.data.db_path), timeout=DB_TIMEOUT_SEC)
    conn.row_factory = sqlite3.Row
    return conn


def _row_to_runstate(row: sqlite3.Row | dict) -> RunState:
    def _get(key: str, default):
        if isinstance(row, dict):
            return row.get(key, default)
        return row[key] if row[key] is not None else default

    return RunState(
        id=_get("ID", ""),
        video_path=Path(_get("VideoPath", "")),
        video_filename=_get("VideoFilename", ""),
        condition=_get("Condition", "A"),
        vlm_provider=_get("VLMProvider", "ollama"),
        model=_get("Model", ""),
        grid_rows=_get("GridRows", 2),
        grid_cols=_get("GridCols", 4),
        sampling_rate=_get("SamplingRate", 24),
        vlm_delay=float(_get("VLMDelay", 0.0)),
        vlm_quantization=_get("VLMQuantization", "none"),
        max_retries=int(_get("MaxRetries", 3)),
        audio_provider=_get("AudioProvider", "panns"),
        audio_model=_get("AudioModel", "cnn14"),
        audio_quantization=_get("AudioQuantization", "none"),
        stage=AnalysisStage(_get("Stage", "queued")) if _get("Stage", None) else AnalysisStage.QUEUED,
    )


class AnalysisServiceImpl(AnalysisService):

    def __init__(self) -> None:
        self._runs: dict[str, RunState] = {}

    def get_run(self, analysis_id: str) -> RunState:
        if analysis_id in self._runs:
            return self._runs[analysis_id]
        run = self._load_run_from_db(analysis_id)
        if run is not None:
            self._runs[analysis_id] = run
            return run
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"unknown analysis_id '{analysis_id}'")

    def get_status(self, analysis_id: str) -> dict:
        run = self.get_run(analysis_id)
        return {
            "id": run.id,
            "condition": run.condition,
            "stage": run.stage.value,
            "counters": run.counters,
            "error": getattr(run, "error", None),
        }

    def stop_analysis(self, analysis_id: str) -> None:
        run = self.get_run(analysis_id)
        if run.stage not in (AnalysisStage.DONE, AnalysisStage.FAILED, AnalysisStage.STOPPED):
            run.stop_event.set()
            run.stage = AnalysisStage.STOPPED

    def delete_analysis(self, analysis_id: str) -> None:
        run = self.get_run(analysis_id)
        cfg = Config.get()
        try:
            conn = _get_db_conn(cfg)
            for table in ("VisualPerFrame", "VisualRelation", "VisualPerInterval",
                          "SoundPerInterval"):
                conn.execute(f"DELETE FROM {table} WHERE AnalysisID = ?", (analysis_id,))
            conn.execute(
                "DELETE FROM VisualParticipant WHERE RelationID IN "
                "(SELECT RelationID FROM VisualPerInterval WHERE AnalysisID = ?)",
                (analysis_id,))
            conn.execute("DELETE FROM Analyses WHERE ID = ?", (analysis_id,))
            conn.commit()
            conn.close()
        except Exception as e:
            log.warning("Failed to delete analysis from DB: %s", e)
        self._runs.pop(analysis_id, None)
        try:
            run.video_path.unlink(missing_ok=True)
        except Exception:
            pass

    def reset_database(self) -> None:
        for run in list(self._runs.values()):
            if run.stage not in (AnalysisStage.DONE, AnalysisStage.FAILED, AnalysisStage.STOPPED):
                run.stop_event.set()
                run.stage = AnalysisStage.STOPPED
        self._runs.clear()
        cfg = Config.get()
        try:
            conn = _get_db_conn(cfg)
            for table in ("VisualParticipant", "VisualPerFrame", "VisualRelation",
                          "VisualPerInterval", "SoundPerInterval", "Analyses"):
                conn.execute(f"DELETE FROM {table}")
            conn.execute("DELETE FROM sqlite_sequence")
            conn.commit()
            conn.close()
            log.info("Reset database: cleared all analysis data")
        except Exception as e:
            log.warning("Failed to reset database: %s", e)

    def start_analysis(
        self,
        *,
        video_path: Path,
        video_filename: str,
        condition: str,
        vlm_provider: str,
        model: str,
        grid_rows: int,
        grid_cols: int,
        sampling_rate: int,
        vlm_delay: float,
        vlm_quantization: str,
        max_retries: int,
        audio_provider: str,
        audio_model: str,
        audio_quantization: str,
        audio_window: float,
        audio_hop: float,
    ) -> RunState:
        analysis_id = uuid.uuid4().hex[:ANALYSIS_ID_HEX_LENGTH]
        cfg = Config.get()

        run = RunState(
            id=analysis_id,
            video_path=video_path,
            video_filename=video_filename,
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
            audio_window=audio_window,
            audio_hop=audio_hop,
        )
        self._runs[analysis_id] = run

        self._persist_analysis_to_db(run, cfg)

        loop = asyncio.get_running_loop()
        loop.run_in_executor(None, self._run_pipeline, run, cfg)

        return run

    def list_analyses(self) -> list[dict]:
        cfg = Config.get()
        try:
            conn = _get_db_conn(cfg)
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT ID, VideoFilename, Condition, VLMProvider, Model, Stage, CreatedAt, CompletedAt "
                "FROM Analyses ORDER BY CreatedAt DESC"
            ).fetchall()
            conn.close()
            return [
                {
                    "id": r["ID"],
                    "video_filename": r["VideoFilename"],
                    "condition": r["Condition"],
                    "vlm_provider": r["VLMProvider"],
                    "model": r["Model"],
                    "stage": r["Stage"],
                    "created_at": r["CreatedAt"],
                    "completed_at": r["CompletedAt"],
                }
                for r in rows
            ]
        except Exception as e:
            log.warning("Failed to list Analyses: %s", e)
            return []

    def detect_event(self, *, analysis_id: str, event_type: str, condition: str, deltas: dict) -> dict:
        run = self.get_run(analysis_id)
        cfg = Config.get()

        if run.stage != AnalysisStage.DONE:
            from fastapi import HTTPException
            raise HTTPException(status_code=409, detail=f"analysis {analysis_id} is not done")

        from service.impl.events_service_impl import events_for_condition, run_sql_detection

        valid_ids = {e.id for e in events_for_condition(condition)}
        if event_type not in valid_ids:
            from fastapi import HTTPException
            raise HTTPException(status_code=400, detail=f"event '{event_type}' not available for condition {condition}")

        rows: list[dict] = []
        try:
            conn = _get_db_conn(cfg)
            try:
                for line in run_sql_detection(conn, event_type, deltas, analysis_id=run.id, condition=condition):
                    if line.startswith("__RESULT__:"):
                        payload = line[len("__RESULT__:"):]
                        try:
                            rows = json.loads(payload)
                        except Exception:
                            rows = []
            finally:
                conn.close()
        except ValueError as e:
            from fastapi import HTTPException
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            from fastapi import HTTPException
            raise HTTPException(status_code=500, detail=f"detection failed: {e}")

        fps = run.sampling_rate
        for row in rows:
            if 'StartFrame' in row:
                row['StartTime'] = _format_time(row['StartFrame'] / fps)
            if 'EndFrame' in row:
                row['EndTime'] = _format_time(row['EndFrame'] / fps)

        return {
            "analysis_id": analysis_id,
            "event_type": event_type,
            "condition": condition,
            "rows": rows,
        }

    def load_from_db(self) -> int:
        cfg = Config.get()
        db_path = Path(cfg.data.db_path)
        if not db_path.exists():
            return 0
        try:
            conn = sqlite3.connect(str(db_path), timeout=DB_TIMEOUT_SEC)
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT ID, VideoPath, VideoFilename, Condition, VLMProvider, Model, "
                "GridRows, GridCols, SamplingRate, VLMDelay, "
                "VLMQuantization, MaxRetries, AudioProvider, AudioModel, AudioQuantization, Stage "
                "FROM Analyses ORDER BY CreatedAt DESC LIMIT 1"
            ).fetchone()
            conn.close()
            if not row or row["ID"] in self._runs:
                return 0
            try:
                run = _row_to_runstate(row)
                self._runs[run.id] = run
                log.info("Restored previous analysis run: %s", run.id)
                return 1
            except Exception as e:
                log.warning("Failed to restore run %s: %s", row["ID"], e)
                return 0
        except Exception as e:
            log.warning("Failed to load run from database: %s", e)
            return 0

    def _load_run_from_db(self, analysis_id: str) -> RunState | None:
        cfg = Config.get()
        try:
            conn = _get_db_conn(cfg)
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT ID, VideoPath, VideoFilename, Condition, VLMProvider, Model, "
                "GridRows, GridCols, SamplingRate, VLMDelay, "
                "VLMQuantization, MaxRetries, AudioProvider, AudioModel, AudioQuantization, Stage "
                "FROM Analyses WHERE ID = ?",
                (analysis_id,),
            ).fetchone()
            conn.close()
            if row:
                return _row_to_runstate(row)
        except Exception:
            pass
        return None

    def _persist_analysis_to_db(self, run: RunState, cfg: Config) -> None:
        try:
            setup_database(Path(cfg.data.db_path))
            conn = _get_db_conn(cfg)
            conn.execute(
                "INSERT INTO Analyses (ID, VideoPath, VideoFilename, Condition, VLMProvider, Model, "
                "GridRows, GridCols, SamplingRate, VLMDelay, VLMQuantization, MaxRetries, "
                "AudioProvider, AudioModel, AudioQuantization, Stage, CreatedAt) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (run.id, str(run.video_path), run.video_filename, run.condition,
                 run.vlm_provider, run.model, run.grid_rows, run.grid_cols,
                 run.sampling_rate, run.vlm_delay, run.vlm_quantization, run.max_retries,
                 run.audio_provider, run.audio_model, run.audio_quantization,
                 run.stage.value, datetime.datetime.now().isoformat()),
            )
            conn.commit()
            conn.close()
        except Exception as e:
            log.warning("Failed to persist analysis metadata: %s", e)

    def _run_vlm(self, run: RunState, conn: sqlite3.Connection, cfg: Config,
                 _log: Callable[[str], None], persist_stage: Callable[[str], None]) -> None:
        from service.impl.visual_service_impl import VisualServiceImpl
        from service.impl.interval_service_impl import IntervalServiceImpl
        from utils.vlm_client import VLMClient

        run.stage = AnalysisStage.VLM
        persist_stage("vlm")
        _log(f">>> CONDITION {run.condition}: visual perception (VLM)")
        _log(f"     Provider: {run.vlm_provider}, Model: {run.model or '(default)'}, "
             f"Grid: {run.grid_rows}x{run.grid_cols}, Sampling: every {run.sampling_rate} frames"
             f", Delay: {run.vlm_delay}s")

        try:
            client = VLMClient(
                provider=run.vlm_provider,
                model=run.model or None,
                base_url=cfg.vlm.ollama_base_url if run.vlm_provider == "ollama" else None,
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
            _log(f"VLM pipeline error: {e}")
            log.info("VLM pipeline error [%s]: %s\n%s", run.id, e, traceback.format_exc())
            raise

        run.stage = AnalysisStage.INTERVAL
        persist_stage("interval")
        _log(">>> PHASE 2 START: interval construction (inside VLM pipeline)")

    def _run_audio(self, run: RunState, conn: sqlite3.Connection, cfg: Config,
                   _log: Callable[[str], None], persist_stage: Callable[[str], None]) -> None:
        from service.impl.audio_service_impl import AudioServiceImpl

        run.stage = AnalysisStage.SOUND
        persist_stage("sound")
        _log(f">>> CONDITION {run.condition}: sound perception ({run.audio_provider})")
        try:
            out_dir = Path(cfg.data.dir) / "audio"
            out_dir.mkdir(parents=True, exist_ok=True)
            audio = AudioServiceImpl(
                audio_provider=run.audio_provider,
                audio_model=run.audio_model or None,
                quantization=run.audio_quantization,
                audio_window=run.audio_window,
                audio_hop=run.audio_hop,
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

    def _run_pipeline(self, run: RunState, cfg: Config) -> None:
        if run.stop_event.is_set():
            return
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        stage_conn: sqlite3.Connection | None = None

        def persist_stage(stage: str) -> None:
            nonlocal stage_conn
            try:
                if stage_conn is None:
                    stage_conn = _get_db_conn(cfg)
                stage_conn.execute(
                    "UPDATE Analyses SET Stage = ? WHERE ID = ?",
                    (stage, run.id),
                )
                stage_conn.commit()
            except Exception as e:
                log.warning("Failed to persist stage for %s: %s", run.id, e)

        async def push(stage: str, msg: str) -> None:
            await run.log_queue.put(make_log_entry(stage, msg))

        def _log(msg: str) -> None:
            try:
                loop.run_until_complete(push(run.stage.value, msg))
            except RuntimeError:
                asyncio.run_coroutine_threadsafe(push(run.stage.value, msg), loop)

        conn = None
        try:
            conn, _cursor = setup_database(Path(cfg.data.db_path))

            if run.condition in ("A", "C"):
                if run.stop_event.is_set():
                    _log(">>> STOPPED before VLM")
                    run.stage = AnalysisStage.STOPPED
                    return
                self._run_vlm(run, conn, cfg, _log, persist_stage)
            else:
                _log(">>> CONDITION B: skipping VLM (sound-only condition)")

            if run.condition in ("B", "C"):
                if run.stop_event.is_set():
                    _log(">>> STOPPED before audio")
                    run.stage = AnalysisStage.STOPPED
                    return
                self._run_audio(run, conn, cfg, _log, persist_stage)
            else:
                _log(">>> CONDITION A: skipping sound pipeline (visual-only condition)")

            if conn is not None:
                conn.close()
            run.stage = AnalysisStage.DONE
            persist_stage("done")
            try:
                if stage_conn is not None:
                    stage_conn.execute(
                        "UPDATE Analyses SET CompletedAt = ? WHERE ID = ?",
                        (datetime.datetime.now().isoformat(), run.id),
                    )
                    stage_conn.commit()
            except Exception as e:
                log.warning("Failed to persist completion time: %s", e)
            _log(">>> ANALYSIS COMPLETE")
        except Exception as e:
            tb = traceback.format_exc()
            _log(f"CRITICAL ERROR: {e}")
            log.info("CRITICAL ERROR [%s]: %s\n%s", run.id, e, tb)
            run.stage = AnalysisStage.FAILED
            run.error = f"{e}\n{tb}"
        finally:
            if stage_conn is not None:
                if run.stage in (AnalysisStage.DONE, AnalysisStage.STOPPED, AnalysisStage.FAILED):
                    try:
                        stage_conn.execute(
                            "UPDATE Analyses SET Stage = ? WHERE ID = ?",
                            (run.stage.value, run.id),
                        )
                        stage_conn.commit()
                    except Exception:
                        pass
                stage_conn.close()
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass
            sentinel = SENTINEL_RUN_FAILED if run.stage == AnalysisStage.FAILED else SENTINEL_RUN_DONE
            loop.run_until_complete(run.log_queue.put(make_log_entry(run.stage.value, sentinel)))
            loop.close()
