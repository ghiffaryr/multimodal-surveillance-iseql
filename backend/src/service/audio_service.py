from abc import ABC, abstractmethod
from pathlib import Path
from typing import Callable, Optional
import sqlite3

class AudioService(ABC):
    @abstractmethod
    def run_pipeline(
        self,
        video_path: Path,
        conn: sqlite3.Connection,
        out_dir: Path,
        fps: int = 30,
        analysis_id: str = "",
        log_fn: Optional[Callable[[str], None]] = None,
    ) -> dict:
        pass
