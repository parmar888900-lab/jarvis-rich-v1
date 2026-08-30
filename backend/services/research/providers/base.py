"""Base class for all research providers."""

from abc import ABC, abstractmethod


class ResearchProvider(ABC):
    """
    Base interface for every research provider.

    Every provider must return a list of facts about a topic.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name."""
        raise NotImplementedError

    @abstractmethod
    def research(self, topic: str) -> list[dict]:
        """
        Research a topic.

        Returns a list of dictionaries.

        Example:
        [
            {
                "title": "...",
                "content": "...",
                "source": "...",
                "url": "...",
                "confidence": 0.95,
            }
        ]
        """
        raise NotImplementedError