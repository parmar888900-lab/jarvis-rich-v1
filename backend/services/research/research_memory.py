"""Persistent research memory."""

from datetime import datetime, timedelta

from backend.services.research.knowledge_pack import KnowledgePack


class ResearchMemory:
    """
    Temporary implementation.

    Will later store/retrieve KnowledgePacks
    from SQLite.
    """

    def __init__(self):
        self.memory = {}

    def get(
        self,
        topic: str,
        max_age_hours: int = 24,
    ) -> KnowledgePack | None:

        key = topic.lower()

        if key not in self.memory:
            return None

        timestamp, pack = self.memory[key]

        if (
            datetime.utcnow() - timestamp
            > timedelta(hours=max_age_hours)
        ):
            del self.memory[key]
            return None

        return pack

    def save(
        self,
        topic: str,
        pack: KnowledgePack,
    ) -> None:

        self.memory[topic.lower()] = (
            datetime.utcnow(),
            pack,
        )

    def clear(self):

        self.memory.clear()