from __future__ import annotations

import json
import shutil
import subprocess
import uuid
from pathlib import Path

from fastapi import File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from models.analysis import AnalysisStage, AnalysisStartResponse, Condition
from utils.config import VALID_CONDITIONS, Config
from utils.api_logger import get_logger
from utils.sse import drain_queue_into_sse
from utils.vlm_client import VLMClient

log = get_logger(__name__)


class AnalysisStartController:
    """Start a new analysis by uploading a video."""
    def __init__(self, analysis_service) -> None:
        self._service = analysis_service

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
        available = Config.get_available_providers()

        if condition not in VALID_CONDITIONS:
            raise HTTPException(status_code=400, detail=f"unknown condition '{condition}'; expected A | B | C")
        if vlm_provider is None:
            vlm_provider = available[0] if available else "ollama"
        if condition in ("A", "C") and vlm_provider not in available:
            raise HTTPException(status_code=400, detail=f"Provider '{vlm_provider}' not available")

        upload_dir = Path(cfg.data.upload_dir)
        upload_dir.mkdir(parents=True, exist_ok=True)
        safe_name = Path(video.filename or "upload.mp4").name
        target_path = upload_dir / f"{uuid.uuid4().hex[:12]}_{safe_name}"
        with target_path.open("wb") as f:
            shutil.copyfileobj(video.file, f)
        log.info("Stored upload as %s (condition=%s)", target_path, condition)

        # Auto-detect video FPS
        try:
            probe = subprocess.check_output(
                ["ffprobe", "-v", "error", "-select_streams", "v:0",
                 "-show_entries", "stream=r_frame_rate",
                 "-of", "json", str(target_path)],
                timeout=10, stderr=subprocess.PIPE,
            )
            info = json.loads(probe)
            fps_str = info["streams"][0].get("r_frame_rate", "24/1")
            num, den = fps_str.split("/")
            fps = int(num) // int(den) if int(den) else 24
            sampling_rate = fps or 24
            log.info("Detected video FPS: %d (from %s)", sampling_rate, fps_str)
        except Exception:
            log.info("Could not detect FPS, using default 24")

        run = self._service.start_analysis(
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
        return AnalysisStartResponse(
            analysis_id=run.id,
            condition=Condition(condition),
            stage=AnalysisStage.QUEUED,
            sampling_rate=sampling_rate,
        )


class AnalysisLogsController:
    def __init__(self, analysis_service) -> None:
        self._service = analysis_service

    async def on_get(self, analysis_id: str) -> StreamingResponse:
        run = self._service.get_run(analysis_id)
        return StreamingResponse(
            drain_queue_into_sse(run.log_queue),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )


class AnalysisStatusController:
    def __init__(self, analysis_service) -> None:
        self._service = analysis_service

    async def on_get(self, analysis_id: str) -> dict:
        return self._service.get_status(analysis_id)


class AnalysisListController:
    def __init__(self, analysis_service) -> None:
        self._service = analysis_service

    async def on_get(self) -> list[dict]:
        return self._service.list_analyses()


class AnalysisDetectController:
    def __init__(self, analysis_service) -> None:
        self._service = analysis_service

    async def on_get(self, analysis_id: str, event_type: str) -> StreamingResponse:
        raise HTTPException(status_code=400, detail="GET /detect is deprecated. Use POST.")

    async def on_post(self, analysis_id: str, event_type: str) -> dict:
        run = self._service.get_run(analysis_id)
        return self._service.detect_event(
            analysis_id=analysis_id,
            event_type=event_type,
            condition=run.condition,
        )


class VLMModelsController:
    async def on_get(self, provider: str = "ollama") -> dict:
        available = Config.get_available_providers()
        if provider not in available:
            raise HTTPException(status_code=400, detail=f"Provider '{provider}' not available")
        try:
            client = VLMClient(provider=provider)
            return {"models": client.list_models()}
        except Exception as e:
            log.warning("Cannot list models for %s: %s", provider, e)
            return {"models": [], "error": str(e)}
