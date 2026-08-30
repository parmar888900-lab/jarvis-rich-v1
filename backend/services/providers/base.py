from abc import ABC, abstractmethod


class TrendProvider(ABC):
    """
    Base class for every trend provider.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name."""
        pass

    @abstractmethod
    def get_trends(self, limit: int = 10) -> list[dict]:
        """
        Returns a list of trending topics.

        Each trend should have:
        {
            "title": str,
            "source": str,
            "score": float,
            "category": str,
            "url": str
        }
        """
        pass