from __future__ import annotations

from iseql import vocabulary


class IseqlVocabularyController:
    """Predicate + participant-class vocabulary for the visual event builder."""

    async def on_get(self) -> dict:
        return vocabulary()
