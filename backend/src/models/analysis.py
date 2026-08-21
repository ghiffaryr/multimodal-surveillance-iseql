from __future__ import annotations

import asyncio
import threading
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

class Condition(str, Enum):
    A = "A"
    B = "B"
    C = "C"

class AnalysisStage(str, Enum):
    QUEUED = "queued"
    VLM = "vlm"
    INTERVAL = "interval"
    AUDIO = "audio"
    AUDIO_INTERVAL = "audio_interval"
    DETECTION = "detection"
    DONE = "done"
    FAILED = "failed"
    STOPPED = "stopped"

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
    embed_provider: str = "huggingface"
    embed_model: str = "google/siglip-base-patch16-224"
    memory_n: int = 3
    memory_top_k: int = 5
    audio_provider: str = "panns"
    audio_model: str = "cnn14"
    audio_quantization: str = "none"
    audio_window: float = 2.5
    audio_hop: float = 1.25
    audio_classes: Optional[List[str]] = None
    audio_keywords: Optional[Dict[str, List[str]]] = None
    stage: AnalysisStage = AnalysisStage.QUEUED
    counters: Dict[str, int] = field(default_factory=dict)
    log_queue: "asyncio.Queue" = field(default_factory=asyncio.Queue)
    error: Optional[str] = None
    stop_event: threading.Event = field(default_factory=threading.Event)


class LogEvent(BaseModel):
    ts: float
    stage: str
    message: str
    extra: Dict[str, Any] = Field(default_factory=dict)

class AnalysisStartRequest(BaseModel):
    condition: Condition = Field(
        Condition.A,
        description=(
            "Ablation condition. A=visual only, "
            "B=audio only (PANNs CNN14), C=full multimodal."
        ),
    )
    vlm_provider: str = Field(None, description="VLM provider name (auto-detected from available API keys)")
    model: str = Field("", description="Provider-specific model name")
    grid_rows: int = Field(2, ge=1, le=10)
    grid_cols: int = Field(4, ge=1, le=10)
    sampling_rate: int = Field(24, ge=1)

class AnalysisStartResponse(BaseModel):
    analysis_id: str
    condition: Condition
    stage: AnalysisStage
    sampling_rate: int = 24

class AnalysisStatusResponse(BaseModel):
    id: str
    condition: Condition
    stage: AnalysisStage
    counters: Dict[str, int] = Field(default_factory=dict)

class AnalysisDetectRequest(BaseModel):
    event_type: str
    deltas: Dict[str, int | float | str]
    unit: str = "seconds"

class EventResult(BaseModel):
    event_type: str
    condition: Condition
    rows: List[Dict[str, Any]] = Field(default_factory=list)

class SchemaResponse(BaseModel):
    app: str
    version: str
    tables: Dict[str, str]
    events: Dict[str, List[str]]
    conditions: List[str]

class EventTypeInfo(BaseModel):
    id: str
    label: str
    delta_visual: Optional[str] = None
    delta_audio: Optional[str] = None
    eta_visual: Optional[str] = None
    eta_audio: Optional[str] = None
    zeta_visual: Optional[str] = None
    zeta_audio: Optional[str] = None
    rho_visual: Optional[str] = None
    rho_audio: Optional[str] = None
    condition: str
