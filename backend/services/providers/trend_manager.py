from typing import List

from .base import TrendProvider


class TrendManager:
    """
    Manages all trend providers and combines their results.
    """

    def __init__(self):
        self.providers: List[TrendProvider] = []

    def register(self, provider: TrendProvider):
        """Register a trend provider."""
        self.providers.append(provider)

    def collect_candidates(
        self,
        per_provider_limit: int = 10,
    ) -> list[dict]:
        """
        Collect candidate trends from every provider.

        No cross-provider ranking or truncation happens here.
        The intelligence layer decides which opportunities are strongest.
        """
        all_trends = []

        for provider in self.providers:
            try:
                trends = provider.get_trends(
                    per_provider_limit
                )
                all_trends.extend(trends)

            except Exception as exc:
                print(
                    f"[TrendManager] "
                    f"{provider.name} failed: {exc}"
                )

        return all_trends

    def get_trends(
        self,
        limit: int = 10,
    ) -> list[dict]:
        """
        Backward-compatible ranked trend collection.
        """
        all_trends = self.collect_candidates(
            per_provider_limit=limit
        )

        all_trends.sort(
            key=lambda trend: trend.get(
                "score",
                0,
            ),
            reverse=True,
        )

        return all_trends[:limit]
