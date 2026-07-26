from abc import ABC, abstractmethod
from typing import Callable, Iterator
import sqlite3

class IntervalService(ABC):
    @abstractmethod
    def build_visual_and_save(
        self,
        conn: sqlite3.Connection,
        sampling_rate: int,
        analysis_id: str = "",
        log_fn: Callable[[str], None] = print,
    ) -> Iterator[str]:
        pass
