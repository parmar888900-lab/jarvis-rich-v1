"""Goal-aware candidate intelligence for production topic selection."""

from __future__ import annotations

from typing import Any


class GoalTopicIntelligence:
    """Apply bounded goal pressure to individual production candidates.

    V1 intentionally supports only goal metrics for which we already have
    a meaningful candidate-level signal. Currently that is ``views``,
    represented by the candidate's viral score.

    Goal intelligence never controls scheduler cadence and never determines
    production eligibility. It only returns a bounded score adjustment.
    """

    MAX_ADJUSTMENT = 5.0

    SUPPORTED_METRICS = frozenset(
        {
            "views",
        }
    )

    def evaluate(
        self,
        candidate: dict[str, Any] | None,
        strategy: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Evaluate how well a candidate aligns with the active goal strategy."""

        if not isinstance(strategy, dict):
            return self._neutral(
                reason="goal_strategy_unavailable",
            )

        if strategy.get("status") != "goal_guided":
            return self._neutral(
                reason="goal_strategy_not_active",
            )

        metric = str(strategy.get("target_metric") or "").strip().lower()

        if metric not in self.SUPPORTED_METRICS:
            return self._neutral(
                reason="unsupported_goal_metric",
                target_metric=metric or None,
            )

        production_priority = self._number(
            strategy.get("production_priority")
        )
        exploitation_bias = self._number(
            strategy.get("exploitation_bias")
        )

        if production_priority is None or exploitation_bias is None:
            return self._neutral(
                reason="invalid_goal_strategy",
                target_metric=metric,
            )

        viral_score = self._candidate_viral_score(candidate)

        if viral_score is None:
            return self._neutral(
                reason="candidate_signal_unavailable",
                target_metric=metric,
            )

        pressure = self._clamp(
            production_priority / 100.0,
            0.0,
            1.0,
        )
        exploitation = self._clamp(
            exploitation_bias,
            0.0,
            1.0,
        )
        candidate_strength = self._clamp(
            viral_score / 100.0,
            0.0,
            1.0,
        )

        # Convert candidate strength from [0, 1] into [-1, 1].
        #
        # 100 viral score -> +1
        #  50 viral score ->  0
        #   0 viral score -> -1
        direction = (candidate_strength - 0.5) * 2.0

        adjustment = (
            direction
            * self.MAX_ADJUSTMENT
            * pressure
            * exploitation
        )

        adjustment = self._clamp(
            adjustment,
            -self.MAX_ADJUSTMENT,
            self.MAX_ADJUSTMENT,
        )

        return {
            "status": "applied",
            "reason": "views_goal_candidate_alignment",
            "target_metric": metric,
            "candidate_signal": "viral_score",
            "candidate_signal_value": round(viral_score, 2),
            "production_priority": round(production_priority, 2),
            "exploitation_bias": round(exploitation, 3),
            "adjustment": round(adjustment, 2),
        }

    @classmethod
    def _candidate_viral_score(
        cls,
        candidate: dict[str, Any] | None,
    ) -> float | None:
        if not isinstance(candidate, dict):
            return None

        for key in (
            "final_score",
            "score",
            "initial_score",
        ):
            value = cls._number(candidate.get(key))

            if value is not None:
                return cls._clamp(value, 0.0, 100.0)

        return None

    @staticmethod
    def _number(value: Any) -> float | None:
        if isinstance(value, bool):
            return None

        if isinstance(value, (int, float)):
            return float(value)

        return None

    @classmethod
    def _neutral(
        cls,
        *,
        reason: str,
        target_metric: str | None = None,
    ) -> dict[str, Any]:
        return {
            "status": "neutral",
            "reason": reason,
            "target_metric": target_metric,
            "candidate_signal": None,
            "candidate_signal_value": None,
            "production_priority": None,
            "exploitation_bias": None,
            "adjustment": 0.0,
        }

    @staticmethod
    def _clamp(
        value: float,
        minimum: float,
        maximum: float,
    ) -> float:
        return min(max(value, minimum), maximum)
