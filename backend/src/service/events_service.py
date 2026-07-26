from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Callable, Iterator, List
import sqlite3

@dataclass
class EventSpec:
    id: str
    label: str
    delta_param: str | None
    condition: str = "A"
    requires_cpp: bool = False
    delta_param2: str | None = None

class EventsService(ABC):
    @abstractmethod
    def queries_for_condition(self, condition: str, deltas: dict) -> dict[str, str]:
        pass

    @abstractmethod
    def events_for_condition(self, condition: str) -> List[EventSpec]:
        pass

    @abstractmethod
    def run_sql_detection(
        self,
        conn: sqlite3.Connection,
        event_type: str,
        deltas: dict,
        condition: str = "A",
        log: Callable[[str], None] = None,
    ) -> Iterator[str]:
        pass
