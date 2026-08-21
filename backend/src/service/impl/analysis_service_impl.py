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


def _projection_extent_aliases(event_type: str, condition: str, specs) -> tuple[str | None, str | None]:
    """Resolve which interval aliases produce the event's start/end frames.

    Returns (start_alias, end_alias) like ``("M1", "M2")`` so the frontend can
    label frame columns ``M1.sf``/``M2.ef`` and time columns ``M1.st``/``M2.et``
    by source interval. Set-operation events derive the extent from the left
    (audio) operand. Falls back to ``(None, None)`` when the model can't be read.
    """
    try:
        import json as _json
        from service.events_service import EventSpec
        spec = next((s for s in (specs or []) if getattr(s, "id", None) == event_type
                     and getattr(s, "condition", None) == condition), None)
        if spec is None or not getattr(spec, "model_json", None):
            return None, None
        model = _json.loads(spec.model_json)
        fields = None
        if any(iv.get("set_side") for iv in model.get("intervals", [])):
            fields = model.get("left_projection")
        else:
            fields = model.get("custom_projection")
        start_alias = end_alias = None
        if fields:
            for f in fields:
                parts = f.split(".")
                if len(parts) == 2 and parts[0].startswith("M") and parts[1] in ("sf", "st", "ef", "et"):
                    if start_alias is None and parts[1] in ("sf", "st"):
                        start_alias = parts[0]
                    if parts[1] in ("ef", "et"):
                        end_alias = parts[0]
        return start_alias, end_alias
    except Exception:
        return None, None


def _get_db_conn(cfg: Config) -> sqlite3.Connection:
    conn = sqlite3.connect(str(cfg.data.db_path), timeout=DB_TIMEOUT_SEC)
    conn.row_factory = sqlite3.Row
    return conn


def _resolve_config_section(conn: sqlite3.Connection, key: str, overrides: dict | None) -> dict:
    """Resolve a config section: AppConfig store baseline merged with per-analysis
    overrides (overrides win). No hardcoded defaults; a missing key surfaces as a
    KeyError in the consuming service."""
    from service.impl.config_store_service_impl import ConfigStoreServiceImpl
    store = ConfigStoreServiceImpl().get_section(conn, key) or {}
    merged = dict(store)
    if overrides:
        merged.update({k: v for k, v in overrides.items() if v is not None})
    return merged


_REQUIRED_RUN_COLUMNS = ("ID", "VideoPath", "VideoFilename", "Condition", "Stage")


def _row_to_runstate(row: sqlite3.Row | dict) -> RunState:
    """Build a RunState from an Analyses row. Required columns are read strictly;
    nullable columns pass through as-is (no silent default substitution)."""

    def _col(key: str):
        try:
            return row[key]
        except (KeyError, IndexError):
            raise ValueError(f"analysis row missing required column '{key}'")

    def _as_int(key: str):
        value = _col(key)
        return int(value) if value is not None else None

    def _as_float(key: str):
        value = _col(key)
        return float(value) if value is not None else None

    def _as_str(key: str, default: str):
        value = _col(key)
        return value if value is not None else default

    for key in _REQUIRED_RUN_COLUMNS:
        if _col(key) is None:
            raise ValueError(f"analysis row column '{key}' is NULL but required")

    return RunState(
        id=_col("ID"),
        video_path=Path(_col("VideoPath")),
        video_filename=_col("VideoFilename"),
        condition=_col("Condition"),
        vlm_provider=_col("VLMProvider"),
        model=_col("Model"),
        grid_rows=_as_int("GridRows"),
        grid_cols=_as_int("GridCols"),
        sampling_rate=_as_int("SamplingRate"),
        vlm_delay=_as_float("VLMDelay"),
        vlm_quantization=_col("VLMQuantization"),
        max_retries=_as_int("MaxRetries"),
        embed_provider=_as_str("EmbedProvider", "huggingface"),
        embed_model=_as_str("EmbedModel", "google/siglip-base-patch16-224"),
        memory_n=_as_int("MemoryN") or 3,
        memory_top_k=_as_int("MemoryTopK") or 5,
        audio_provider=_col("AudioProvider"),
        audio_model=_col("AudioModel"),
        audio_quantization=_col("AudioQuantization"),
        stage=AnalysisStage(_col("Stage")),
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
                          "AudioPerInterval"):
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
        # Safety: only analysis data is cleared. AppConfig and EventSpec
        # (user settings + event definitions) are NEVER touched here; they
        # survive a reset.
        analysis_tables = ("VisualParticipant", "VisualPerFrame", "VisualRelation",
                           "VisualPerInterval", "AudioPerInterval", "Analyses")
        try:
            conn = _get_db_conn(cfg)
            for table in analysis_tables:
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
        embed_provider: str = "huggingface",
        embed_model: str = "google/siglip-base-patch16-224",
        memory_n: int = 3,
        memory_top_k: int = 5,
        audio_provider: str,
        audio_model: str,
        audio_quantization: str,
        audio_window: float,
        audio_hop: float,
        audio_classes: list[str] | None = None,
        audio_keywords: dict[str, list[str]] | None = None,
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
            embed_provider=embed_provider,
            embed_model=embed_model,
            memory_n=memory_n,
            memory_top_k=memory_top_k,
            audio_provider=audio_provider,
            audio_model=audio_model,
            audio_quantization=audio_quantization,
            audio_window=audio_window,
            audio_hop=audio_hop,
            audio_classes=audio_classes,
            audio_keywords=audio_keywords,
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
                "SELECT ID, VideoFilename, Condition, VLMProvider, Model, Stage, SamplingRate, CreatedAt, CompletedAt "
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
                    "sampling_rate": r["SamplingRate"],
                    "created_at": r["CreatedAt"],
                    "completed_at": r["CompletedAt"],
                }
                for r in rows
            ]
        except Exception as e:
            log.warning("Failed to list Analyses: %s", e)
            return []

    def detect_event(self, *, analysis_id: str, event_type: str, condition: str,
                     deltas: dict, unit: str = "seconds") -> dict:
        run = self.get_run(analysis_id)
        cfg = Config.get()

        if run.stage != AnalysisStage.DONE:
            from fastapi import HTTPException
            raise HTTPException(status_code=409, detail=f"analysis {analysis_id} is not done")

        from service.impl.events_service_impl import events_for_condition, run_sql_detection

        if unit == "seconds":
            fps = run.sampling_rate
            deltas = {
                k: (round(v * fps) if isinstance(v, (int, float)) and not isinstance(v, bool) else v)
                for k, v in deltas.items()
            }

        rows: list[dict] = []
        conn_specs = None
        try:
            conn = _get_db_conn(cfg)
            try:
                valid_ids = {e.id for e in events_for_condition(condition, conn=conn)}
                if event_type not in valid_ids:
                    raise HTTPException(status_code=400, detail=f"event '{event_type}' not available for condition {condition}")
                conn_specs = events_for_condition(condition, conn=conn)
                for line in run_sql_detection(conn, event_type, deltas, analysis_id=run.id, condition=condition,
                                              fps=run.sampling_rate):
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
        start_alias, end_alias = _projection_extent_aliases(event_type, condition, conn_specs or None)
        for row in rows:
            st_key = f"{start_alias}.st" if start_alias else None
            et_key = f"{end_alias}.et" if end_alias else None
            sf_key = f"{start_alias}_sf" if start_alias else None
            ef_key = f"{end_alias}_ef" if end_alias else None
            # time-domain: the query already projected st/et (time floats)
            if st_key and st_key in row and row[st_key] is not None and not isinstance(row[st_key], str):
                row[st_key] = _format_time(row[st_key])
            if et_key and et_key in row and row[et_key] is not None and not isinstance(row[et_key], str):
                row[et_key] = _format_time(row[et_key])
            # frame-domain: derive st/et from the projected sf/ef frames
            sf = row.get(sf_key) if sf_key else None
            ef = row.get(ef_key) if ef_key else None
            if st_key is None and sf is not None and start_alias:
                row[st_key] = _format_time(sf / fps)
            if et_key is None and ef is not None and end_alias:
                row[et_key] = _format_time(ef / fps)

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
                "GridRows, GridCols, SamplingRate, VLMDelay, VLMQuantization, MaxRetries, "
                "EmbedProvider, EmbedModel, MemoryN, MemoryTopK, AudioProvider, AudioModel, AudioQuantization, Stage "
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
                "GridRows, GridCols, SamplingRate, VLMDelay, VLMQuantization, MaxRetries, "
                "EmbedProvider, EmbedModel, MemoryN, MemoryTopK, AudioProvider, AudioModel, AudioQuantization, Stage "
                "FROM Analyses WHERE ID = ?",
                (analysis_id,),
            ).fetchone()
            conn.close()
            if row:
                return _row_to_runstate(row)
        except Exception as e:
            log.warning("Failed to load run %s from DB: %s", analysis_id, e)
        return None

    def _persist_analysis_to_db(self, run: RunState, cfg: Config) -> None:
        try:
            setup_database(Path(cfg.data.db_path))
            conn = _get_db_conn(cfg)
            conn.execute(
                "INSERT INTO Analyses (ID, VideoPath, VideoFilename, Condition, VLMProvider, Model, "
                "GridRows, GridCols, SamplingRate, VLMDelay, VLMQuantization, MaxRetries, "
                "EmbedProvider, EmbedModel, MemoryN, MemoryTopK, "
                "AudioProvider, AudioModel, AudioQuantization, Stage, CreatedAt) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (run.id, str(run.video_path), run.video_filename, run.condition,
                 run.vlm_provider, run.model, run.grid_rows, run.grid_cols,
                 run.sampling_rate, run.vlm_delay, run.vlm_quantization, run.max_retries,
                 run.embed_provider, run.embed_model, run.memory_n, run.memory_top_k,
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
        _log(f"     Object tracking: enabled | Embedding: "
             f"{run.embed_provider}:{run.embed_model}")

        try:
            client = VLMClient(
                provider=run.vlm_provider,
                model=run.model or None,
                base_url=cfg.vlm.ollama_base_url if run.vlm_provider == "ollama" else None,
                timeout=float(cfg.vlm.timeout),
            )
            vocab = _resolve_config_section(conn, "relation_vocab", None)
            visual = VisualServiceImpl(
                max_retries=run.max_retries,
                relation_classids=vocab.get("relation_classids"),
                relation_descriptions=vocab.get("relation_descriptions"),
                memory_db_dir=str(Path(cfg.data.dir) / "vector_db"),
                embed_provider=run.embed_provider,
                embed_model=run.embed_model,
                memory_n=run.memory_n,
                memory_top_k=run.memory_top_k,
                ollama_base_url=cfg.vlm.ollama_base_url,
            )
            visual.run_pipeline(
                video_path=str(run.video_path),
                conn=conn,
                client=client,
                grid_rows=run.grid_rows,
                grid_cols=run.grid_cols,
                sampling_rate=run.sampling_rate,
                min_interval=run.vlm_delay,
                analysis_id=run.id,
                track_objects=True,
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

        run.stage = AnalysisStage.AUDIO
        persist_stage("audio")
        _log(f">>> CONDITION {run.condition}: audio perception ({run.audio_provider})")
        try:
            out_dir = Path(cfg.data.dir) / "audio"
            out_dir.mkdir(parents=True, exist_ok=True)
            taxonomy = _resolve_config_section(conn, "audio_taxonomy", {
                "classes": run.audio_classes,
                "keywords": run.audio_keywords,
            })
            audio = AudioServiceImpl(
                audio_provider=run.audio_provider,
                audio_model=run.audio_model or None,
                quantization=run.audio_quantization,
                audio_window=run.audio_window,
                audio_hop=run.audio_hop,
                classes=taxonomy["classes"],
                keywords=taxonomy["keywords"],
            )
            result = audio.run_pipeline(
                video_path=run.video_path,
                conn=conn,
                out_dir=out_dir,
                fps=run.sampling_rate,
                analysis_id=run.id,
                log_fn=_log,
            )
            _log(f"     {result['n_audio_events']} per-frame rows persisted")
        except Exception as e:
            _log(f"audio pipeline error: {e}")
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
                _log(">>> CONDITION B: skipping VLM (audio-only condition)")

            if run.condition in ("B", "C"):
                if run.stop_event.is_set():
                    _log(">>> STOPPED before audio")
                    run.stage = AnalysisStage.STOPPED
                    return
                self._run_audio(run, conn, cfg, _log, persist_stage)
            else:
                _log(">>> CONDITION A: skipping audio pipeline (visual-only condition)")

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
