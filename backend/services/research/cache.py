"""Simple in-memory cache for research results."""

from datetime import datetime, timedelta


class ResearchCache:
    def __init__(self, ttl_minutes: int = 30):
        self.ttl = timedelta(minutes=ttl_minutes)
        self.cache: dict[str, tuple[datetime, dict]] = {}

    def get(self, topic: str):
        item = self.cache.get(topic.lower())

        if item is None:
            return None

        timestamp, value = item

        if datetime.utcnow() - timestamp > self.ttl:
            del self.cache[topic.lower()]
            return None

        return value

    def set(self, topic: str, value: dict):
        self.cache[topic.lower()] = (
            datetime.utcnow(),
            value,
        )

    def clear(self):
        self.cache.clear()