"""Central trend intelligence engine."""

from backend.services.research.research_service import ResearchService

from .deduplicator import TrendDeduplicator
from .scorer import TrendScorer


class TrendEngine:
    """Central intelligence engine for ranking trend opportunities."""

    def __init__(self):
        self.deduplicator = TrendDeduplicator()
        self.scorer = TrendScorer()
        self.research = ResearchService()

    def process(
        self,
        trends: list[dict],
        limit: int = 10,
    ) -> list[dict]:
        """Process raw trends and return the best opportunities."""

        if not trends:
            return []

        # ---------------------------------------------------------------
        # 1. Remove duplicate / highly similar trends.
        # ---------------------------------------------------------------
        unique_trends = self.deduplicator.deduplicate(trends)

        if not unique_trends:
            return []

        # ---------------------------------------------------------------
        # 2. Cheap first-pass scoring.
        #
        # We do not research every trend.
        # ---------------------------------------------------------------
        for trend in unique_trends:
            trend["initial_score"] = self.scorer.score(trend)

        unique_trends.sort(
            key=lambda trend: trend["initial_score"],
            reverse=True,
        )

        # ---------------------------------------------------------------
        # 3. Select only the strongest candidates for research.
        # ---------------------------------------------------------------
        research_count = min(
            max(limit * 2, 5),
            10,
            len(unique_trends),
        )

        candidates = unique_trends[:research_count]

        # ---------------------------------------------------------------
        # 4. Research candidates.
        # ---------------------------------------------------------------
        for trend in candidates:
            topic = trend.get("title", "").strip()

            if not topic:
                trend["knowledge"] = {}
                trend["viral_score"] = trend["initial_score"]
                continue

            try:
                knowledge = self.research.research(topic)
                trend["knowledge"] = knowledge.to_dict()

            except Exception as exc:
                print(
                    f"[TrendEngine] Research failed for "
                    f"'{topic}': {exc}"
                )

                trend["knowledge"] = {}

            # -----------------------------------------------------------
            # 5. Final score using research quality.
            # -----------------------------------------------------------
            trend["viral_score"] = self.scorer.score(trend)

        # ---------------------------------------------------------------
        # 6. Final ranking.
        # ---------------------------------------------------------------
        candidates.sort(
            key=lambda trend: trend["viral_score"],
            reverse=True,
        )

        # ---------------------------------------------------------------
        # 7. Return the requested number.
        # ---------------------------------------------------------------
        return candidates[:limit]