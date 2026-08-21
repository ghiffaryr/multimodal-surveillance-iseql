from abc import ABC, abstractmethod
from typing import Optional
import sqlite3

from service.events_service import EventSpec


class EventRegistryService(ABC):
    """DB-backed event registry: the runtime source of truth for event specs.

    Events are CRUD-able (create/update/delete/enable) and compiled to SQL at
    detection time (compile-at-detect). The registry is seeded at startup from
    the built-in events so the app works before any event is edited.
    """

    @abstractmethod
    def list_events(
        self,
        conn: sqlite3.Connection,
        condition: Optional[str] = None,
    ) -> list[EventSpec]:
        pass

    @abstractmethod
    def get_event(
        self, conn: sqlite3.Connection, event_id: str, condition: str
    ) -> Optional[EventSpec]:
        pass

    @abstractmethod
    def create_event(self, conn: sqlite3.Connection, spec: EventSpec) -> EventSpec:
        pass

    @abstractmethod
    def update_event(
        self, conn: sqlite3.Connection, event_id: str, condition: str, fields: dict
    ) -> EventSpec:
        pass

    @abstractmethod
    def delete_event(
        self, conn: sqlite3.Connection, event_id: str, condition: str
    ) -> None:
        pass

    @abstractmethod
    def required_deltas(self, conn: sqlite3.Connection, condition: str) -> set[str]:
        """Delta-parameter names required by the events of a condition."""
        pass
