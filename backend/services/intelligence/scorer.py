"""Trend opportunity scoring for Jarvis."""

import math
from datetime import datetime, timezone


class TrendScorer:
    """Calculate a normalized 0-100 opportunity score."""

    SOURCE_PRIORS = {
        "YouTube": 15.0,
        "Google News RSS": 13.0,
        "Reddit": 12.0,
    }

    MAX_SOURCE_SCORE = 15.0
    MAX_PROVIDER_SCORE = 30.0
    MAX_ENGAGEMENT_SCORE = 25.0
    MAX_FRESHNESS_SCORE = 20.0
    MAX_RESEARCH_SCORE = 10.0

    def score(self, trend: dict) -> float:
        """Return a normalized opportunity score."""

        source_score = self._source_score(trend)
        provider_score = self._provider_strength(trend)
        engagement_score = self._engagement_score(trend)
        freshness_score = self._freshness_score(trend)
        research_score = self._research_score(trend)

        total = (
            source_score
            + provider_score
            + engagement_score
            + freshness_score
            + research_score
        )

        return round(
            min(max(total, 0.0), 100.0),
            2,
        )

    def _source_score(self, trend: dict) -> float:
        source = trend.get("source", "")

        return self.SOURCE_PRIORS.get(
            source,
            10.0,
        )

    def _provider_strength(self, trend: dict) -> float:
        """
        Normalize provider-specific strength.

        Provider APIs use different score scales, so raw values
        must not be compared directly across providers.
        """

        source = trend.get("source", "")
        raw_score = max(
            float(trend.get("score", 0) or 0),
            0.0,
        )

        if source == "YouTube":
            # YouTube scores can range from single digits
            # into the hundreds or thousands. Log scaling
            # preserves separation without allowing huge
            # values to dominate the final score.
            normalized = (
                math.log1p(raw_score)
                / math.log1p(600.0)
            )

        elif source == "Google News RSS":
            # Current RSS provider assigns rank scores
            # beginning near 80. Convert that ranking
            # signal into a bounded 0-1 strength.
            normalized = (
                (raw_score - 60.0)
                / 20.0
            )

        elif source == "Reddit":
            # RedditProvider already produces an
            # approximately 0-100 opportunity score.
            normalized = raw_score / 100.0

        else:
            # Conservative generic fallback.
            normalized = raw_score / 100.0

        normalized = min(
            max(normalized, 0.0),
            1.0,
        )

        return round(
            normalized * self.MAX_PROVIDER_SCORE,
            2,
        )

    def _engagement_score(self, trend: dict) -> float:
        """
        Score measurable audience engagement.

        Logarithmic scaling prevents a single viral item
        from overwhelming every other signal.
        """

        views = max(
            int(trend.get("views", 0) or 0),
            0,
        )
        likes = max(
            int(trend.get("likes", 0) or 0),
            0,
        )

        view_score = 0.0
        like_score = 0.0

        if views:
            view_score = min(
                math.log1p(views)
                / math.log1p(10_000_000)
                * 17.0,
                17.0,
            )

        if likes:
            like_score = min(
                math.log1p(likes)
                / math.log1p(500_000)
                * 8.0,
                8.0,
            )

        return round(
            min(
                view_score + like_score,
                self.MAX_ENGAGEMENT_SCORE,
            ),
            2,
        )

    def _freshness_score(self, trend: dict) -> float:
        published = trend.get("published")

        if not published:
            return 0.0

        try:
            published_dt = datetime.fromisoformat(
                str(published).replace(
                    "Z",
                    "+00:00",
                )
            )

            if published_dt.tzinfo is None:
                published_dt = published_dt.replace(
                    tzinfo=timezone.utc
                )

            hours_old = max(
                (
                    datetime.now(timezone.utc)
                    - published_dt
                ).total_seconds()
                / 3600.0,
                0.0,
            )

        except (TypeError, ValueError):
            return 0.0

        if hours_old < 6:
            return 20.0

        if hours_old < 24:
            return 17.0

        if hours_old < 72:
            return 12.0

        if hours_old < 168:
            return 6.0

        return 0.0

    def _research_score(self, trend: dict) -> float:
        knowledge = trend.get("knowledge") or {}

        facts = knowledge.get("facts") or []
        sources = knowledge.get("sources") or []

        fact_score = min(
            len(facts) * 1.5,
            6.0,
        )

        source_score = min(
            len(sources) * 1.0,
            4.0,
        )

        return round(
            min(
                fact_score + source_score,
                self.MAX_RESEARCH_SCORE,
            ),
            2,
        )
