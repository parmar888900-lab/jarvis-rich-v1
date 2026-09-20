"""Central trend intelligence engine."""

from collections import defaultdict

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

        if not trends or limit <= 0:
            return []

        # ---------------------------------------------------------------
        # 1. Remove duplicate / highly similar trends.
        # ---------------------------------------------------------------
        unique_trends = self.deduplicator.deduplicate(
            trends
        )

        if not unique_trends:
            return []

        # ---------------------------------------------------------------
        # 2. Cheap first-pass scoring.
        # ---------------------------------------------------------------
        for trend in unique_trends:
            trend["initial_score"] = self.scorer.score(
                trend
            )

        unique_trends.sort(
            key=lambda trend: trend["initial_score"],
            reverse=True,
        )

        # ---------------------------------------------------------------
        # 3. Select a diversified research shortlist.
        #
        # Initial provider scores are not perfectly comparable.
        # Preserve strong candidates from every active source before
        # filling remaining research slots globally.
        # ---------------------------------------------------------------
        research_count = min(
            max(limit * 2, 5),
            10,
            len(unique_trends),
        )

        candidates = self._select_research_candidates(
            unique_trends,
            research_count,
        )

        # ---------------------------------------------------------------
        # 4. Research candidates.
        # ---------------------------------------------------------------
        for trend in candidates:
            topic = trend.get(
                "title",
                "",
            ).strip()

            if not topic:
                trend["knowledge"] = {}
                trend["viral_score"] = trend[
                    "initial_score"
                ]
                continue

            try:
                knowledge = self.research.research(
                    topic
                )
                trend["knowledge"] = (
                    knowledge.to_dict()
                )

            except Exception as exc:
                print(
                    f"[TrendEngine] Research failed for "
                    f"'{topic}': {exc}"
                )

                trend["knowledge"] = {}

            # -----------------------------------------------------------
            # 5. Final score using research quality.
            # -----------------------------------------------------------
            trend["viral_score"] = self.scorer.score(
                trend
            )

        # ---------------------------------------------------------------
        # 6. Final cross-source ranking.
        # ---------------------------------------------------------------
        candidates.sort(
            key=lambda trend: trend["viral_score"],
            reverse=True,
        )

        # ---------------------------------------------------------------
        # 7. Return the requested number.
        # ---------------------------------------------------------------
        return candidates[:limit]

    @staticmethod
    def _select_research_candidates(
        trends: list[dict],
        research_count: int,
    ) -> list[dict]:
        """
        Build a source-diverse research shortlist.

        Half of the available research budget is reserved for
        source representation. Those slots are distributed as
        evenly as possible across active sources.

        Remaining slots are filled by initial score regardless
        of source.
        """

        if research_count <= 0:
            return []

        if len(trends) <= research_count:
            return list(trends)

        by_source = defaultdict(list)

        for trend in trends:
            source = (
                trend.get("source")
                or "Unknown"
            )
            by_source[source].append(trend)

        # A single-source pool needs no diversification.
        if len(by_source) <= 1:
            return trends[:research_count]

        # Every source bucket inherits the global initial-score
        # ordering, but sort explicitly so this helper is safe
        # when called independently.
        for source_trends in by_source.values():
            source_trends.sort(
                key=lambda trend: trend.get(
                    "initial_score",
                    0,
                ),
                reverse=True,
            )

        selected = []
        selected_ids = set()

        # Reserve approximately half the research budget for
        # source diversity.
        diversity_budget = max(
            len(by_source),
            research_count // 2,
        )
        diversity_budget = min(
            diversity_budget,
            research_count,
        )

        source_names = sorted(
            by_source,
            key=lambda source: (
                by_source[source][0].get(
                    "initial_score",
                    0,
                )
            ),
            reverse=True,
        )

        # Round-robin selection prevents one provider from
        # consuming the entire diversity budget.
        source_positions = {
            source: 0
            for source in source_names
        }

        while (
            len(selected) < diversity_budget
        ):
            added = False

            for source in source_names:
                if (
                    len(selected)
                    >= diversity_budget
                ):
                    break

                position = source_positions[
                    source
                ]
                source_trends = by_source[
                    source
                ]

                if position >= len(source_trends):
                    continue

                trend = source_trends[position]

                source_positions[source] += 1

                trend_id = id(trend)

                if trend_id in selected_ids:
                    continue

                selected.append(trend)
                selected_ids.add(trend_id)
                added = True

            if not added:
                break

        # Fill the remaining research capacity with the
        # strongest candidates globally.
        for trend in trends:
            if len(selected) >= research_count:
                break

            trend_id = id(trend)

            if trend_id in selected_ids:
                continue

            selected.append(trend)
            selected_ids.add(trend_id)

        return selected
