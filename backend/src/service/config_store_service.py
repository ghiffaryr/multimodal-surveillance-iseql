from abc import ABC, abstractmethod
from typing import Optional
import sqlite3


class ConfigStoreService(ABC):
    """DB-backed application configuration store.

    The production "traits" (audio taxonomy, relation vocabulary) are defined
    by the user in the settings frontend and persisted here. Nothing is
    hardcoded in the backend: the pipeline resolves each section from this
    store, then layers per-analysis overrides on top.
    """

    @abstractmethod
    def get_section(self, conn: sqlite3.Connection, key: str) -> Optional[dict]:
        """Return the stored section dict, or None if not configured yet."""
        pass

    @abstractmethod
    def set_section(self, conn: sqlite3.Connection, key: str, value: dict) -> None:
        """Upsert a section (replace whole value)."""
        pass

    @abstractmethod
    def list_sections(self, conn: sqlite3.Connection) -> dict[str, dict]:
        """Return all stored sections keyed by name."""
        pass

    @abstractmethod
    def delete_section(self, conn: sqlite3.Connection, key: str) -> None:
        pass
