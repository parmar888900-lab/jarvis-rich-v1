"""Production topic selection for YouTube automation."""

from __future__ import annotations

from typing import Any

from backend.services.intelligence.suitability import (
    TopicSuitabilityScorer,
)


class ProductionTopicSelector:
    """
    Selects the strongest production-ready topic.

    Viral potential and production suitability remain separate signals.

    The selector rejects candidates that do not meet minimum research
    confidence or suitability requirements, then ranks the remaining
    candidates using a bounded composite production score.
    """

    MIN_SUITABILITY = 40.0
    MIN_RESEARCH_CONFIDENCE = 35.0
    MAX_LOW_CONTEXT_PENALTY = 16.0

    VIRAL_WEIGHT = 0.35
    SUITABILITY_WEIGHT = 0.45
    RESEARCH_WEIGHT = 0.20

    def __init__(self) -> None:
        self.suitability = TopicSuitabilityScorer()

    def select(
        self,
        trends: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        """
        Return the strongest production-ready trend.

        Each candidate receives:
            - viral score
            - research confidence
            - suitability score
            - production score
            - selection metadata

        Rejected candidates remain annotated so callers can explain why
        they were not selected.
        """

        if not trends:
            return None

        eligible: list[dict[str, Any]] = []

        for trend in trends:
            self._evaluate(trend)

            selection = trend["production_selection"]

            if selection["eligible"]:
                eligible.append(trend)

        if not eligible:
            return None

        eligible.sort(
            key=lambda trend: (
                trend["production_selection"][
                    "production_score"
                ],
                trend["production_selection"][
                    "suitability_score"
                ],
                trend["production_selection"][
                    "viral_score"
                ],
            ),
            reverse=True,
        )

        winner = eligible[0]

        winner["production_selection"][
            "selected"
        ] = True

        winner["production_selection"][
            "reason"
        ] = (
            "Highest production score among candidates "
            "that passed research-confidence and "
            "topic-suitability thresholds."
        )

        return winner

    def rank(
        self,
        trends: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        Evaluate and rank all candidates.

        Eligible candidates appear first, followed by rejected candidates.
        """

        evaluated: list[dict[str, Any]] = []

        for trend in trends:
            self._evaluate(trend)
            evaluated.append(trend)

        return sorted(
            evaluated,
            key=lambda trend: (
                trend["production_selection"][
                    "eligible"
                ],
                trend["production_selection"][
                    "production_score"
                ],
            ),
            reverse=True,
        )

    def _evaluate(
        self,
        trend: dict[str, Any],
    ) -> None:

        suitability = self.suitability.score(
            trend
        )

        viral_score = self._viral_score(trend)
        research_score = self._research_score(trend)
        suitability_score = float(
            suitability["score"]
        )

        rejection_reasons: list[str] = []

        if (
            research_score
            < self.MIN_RESEARCH_CONFIDENCE
        ):
            rejection_reasons.append(
                "research_confidence_below_threshold"
            )

        if (
            suitability_score
            < self.MIN_SUITABILITY
        ):
            rejection_reasons.append(
                "suitability_below_threshold"
            )

        low_context_penalty = float(
            suitability.get(
                "low_context_penalty",
                0.0,
            )
        )

        if (
            low_context_penalty
            >= self.MAX_LOW_CONTEXT_PENALTY
        ):
            rejection_reasons.append(
                "low_context_media"
            )

        eligible = not rejection_reasons

        production_score = (
            viral_score * self.VIRAL_WEIGHT
            + suitability_score
            * self.SUITABILITY_WEIGHT
            + research_score
            * self.RESEARCH_WEIGHT
        )

        trend["production_selection"] = {
            "eligible": eligible,
            "selected": False,
            "viral_score": round(
                viral_score,
                2,
            ),
            "research_confidence": round(
                research_score,
                2,
            ),
            "suitability_score": round(
                suitability_score,
                2,
            ),
            "production_score": round(
                production_score,
                2,
            ),
            "rejection_reasons": (
                rejection_reasons
            ),
            "suitability": suitability,
            "reason": (
                "Eligible for production."
                if eligible
                else "Rejected before production."
            ),
        }

    @staticmethod
    def _viral_score(
        trend: dict[str, Any],
    ) -> float:

        for key in (
            "final_score",
            "score",
            "initial_score",
        ):
            value = trend.get(key)

            if value is None:
                continue

            try:
                return min(
                    max(float(value), 0.0),
                    100.0,
                )
            except (TypeError, ValueError):
                continue

        return 0.0

    @staticmethod
    def _research_score(
        trend: dict[str, Any],
    ) -> float:

        knowledge = trend.get("knowledge")

        if not isinstance(knowledge, dict):
            return 0.0

        try:
            value = float(
                knowledge.get("score", 0.0)
            )
        except (TypeError, ValueError):
            return 0.0

        return min(
            max(value, 0.0),
            100.0,
        )
