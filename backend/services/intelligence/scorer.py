"""Trend opportunity scoring for Jarvis."""

from datetime import datetime, timezone


class TrendScorer:
    """
    Calculates a deterministic opportunity score for a trend.

    The scorer is intentionally based only on information that Jarvis
    currently has available.
    """

    SOURCE_WEIGHTS = {
        "YouTube": 25.0,
        "Google News RSS": 20.0,
    }

    def score(self, trend: dict) -> float:
        score = 0.0

        source = trend.get("source", "")
        score += self.SOURCE_WEIGHTS.get(source, 10.0)

        # Provider's own score.
        provider_score = float(trend.get("score", 0) or 0)
        score += min(provider_score, 50.0)

        # YouTube engagement signals.
        views = int(trend.get("views", 0) or 0)
        likes = int(trend.get("likes", 0) or 0)

        score += min(views / 1_000_000 * 10.0, 10.0)
        score += min(likes / 100_000 * 5.0, 5.0)

        # Freshness.
        published = trend.get("published")

        if published:
            try:
                published_dt = datetime.fromisoformat(
                    published.replace("Z", "+00:00")
                )

                hours_old = (
                    datetime.now(timezone.utc) - published_dt
                ).total_seconds() / 3600

                if hours_old < 6:
                    score += 12.0
                elif hours_old < 24:
                    score += 10.0
                elif hours_old < 72:
                    score += 6.0
                elif hours_old < 168:
                    score += 3.0

            except (TypeError, ValueError):
                pass

        # Research quality bonus.
        knowledge = trend.get("knowledge") or {}

        facts = knowledge.get("facts") or []
        sources = knowledge.get("sources") or []

        score += min(len(facts) * 1.5, 6.0)
        score += min(len(sources) * 1.0, 4.0)

        return round(score, 2)