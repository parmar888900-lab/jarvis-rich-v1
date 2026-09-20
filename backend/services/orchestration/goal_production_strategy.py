"""Goal-aware production strategy.

Converts evaluated Jarvis goals into bounded strategic guidance for
production decisions. This layer does not schedule production, mutate
goals, or directly change upload frequency.
"""

from __future__ import annotations

from typing import Any


class GoalProductionStrategy:
    """Translate goal evaluations into safe production guidance."""

    NEUTRAL_PRIORITY = 50.0

    TRAJECTORY_PRIORITY = {
        "ahead": 40.0,
        "on_track": 55.0,
        "behind": 75.0,
    }

    TRAJECTORY_EXPLOITATION = {
        "ahead": 0.50,
        "on_track": 0.60,
        "behind": 0.75,
    }

    ACTIVE_STATUS = "active"

    def build(
        self,
        goals: list[dict[str, Any]] | None,
    ) -> dict[str, Any]:
        """Build one production strategy from evaluated goals."""

        source_goals = (
            goals
            if isinstance(goals, list)
            else []
        )

        active_goals = [
            goal
            for goal in source_goals
            if (
                isinstance(goal, dict)
                and goal.get("status")
                == self.ACTIVE_STATUS
                and goal.get("trajectory")
                in self.TRAJECTORY_PRIORITY
            )
        ]

        if not active_goals:
            return self._neutral_strategy()

        ranked = sorted(
            active_goals,
            key=self._goal_priority_key,
            reverse=True,
        )

        primary = ranked[0]

        trajectory = str(
            primary["trajectory"]
        )

        urgency = self._urgency(
            primary
        )

        base_priority = (
            self.TRAJECTORY_PRIORITY[
                trajectory
            ]
        )

        production_priority = self._clamp(
            base_priority
            + urgency * 15.0,
            0.0,
            100.0,
        )

        exploitation_bias = self._clamp(
            self.TRAJECTORY_EXPLOITATION[
                trajectory
            ]
            + urgency * 0.10,
            0.0,
            0.85,
        )

        exploration_bias = (
            1.0
            - exploitation_bias
        )

        return {
            "status": "goal_guided",
            "active_goal_count": len(
                active_goals
            ),
            "primary_goal": {
                "goal_id": primary.get(
                    "goal_id"
                ),
                "name": primary.get(
                    "name"
                ),
                "metric": primary.get(
                    "metric"
                ),
                "trajectory": trajectory,
                "progress_percent": (
                    primary.get(
                        "progress_percent"
                    )
                ),
                "time_progress_percent": (
                    primary.get(
                        "time_progress_percent"
                    )
                ),
                "remaining_days": (
                    primary.get(
                        "remaining_days"
                    )
                ),
                "required_daily_rate": (
                    primary.get(
                        "required_daily_rate"
                    )
                ),
                "pace_ratio": primary.get(
                    "pace_ratio"
                ),
            },
            "target_metric": primary.get(
                "metric"
            ),
            "trajectory": trajectory,
            "urgency": round(
                urgency,
                3,
            ),
            "production_priority": round(
                production_priority,
                2,
            ),
            "exploration_bias": round(
                exploration_bias,
                3,
            ),
            "exploitation_bias": round(
                exploitation_bias,
                3,
            ),
            "scheduler_interval_multiplier": 1.0,
            "rationale": self._rationale(
                trajectory
            ),
        }

    def _goal_priority_key(
        self,
        goal: dict[str, Any],
    ) -> tuple[float, float]:
        """Rank active goals by trajectory pressure and urgency."""

        trajectory = str(
            goal.get(
                "trajectory",
                "",
            )
        )

        base = self.TRAJECTORY_PRIORITY.get(
            trajectory,
            0.0,
        )

        return (
            base,
            self._urgency(goal),
        )

    def _urgency(
        self,
        goal: dict[str, Any],
    ) -> float:
        """Return bounded deadline urgency from zero to one."""

        remaining_days = self._number(
            goal.get(
                "remaining_days"
            )
        )

        if remaining_days is None:
            return 0.0

        if remaining_days <= 0:
            return 1.0

        if remaining_days >= 7:
            return 0.0

        return self._clamp(
            1.0
            - remaining_days / 7.0,
            0.0,
            1.0,
        )

    @staticmethod
    def _number(
        value: Any,
    ) -> float | None:
        """Convert safe numeric values without accepting booleans."""

        if isinstance(value, bool):
            return None

        if isinstance(
            value,
            (int, float),
        ):
            return float(value)

        return None

    @staticmethod
    def _clamp(
        value: float,
        minimum: float,
        maximum: float,
    ) -> float:
        return max(
            minimum,
            min(
                maximum,
                value,
            ),
        )

    @classmethod
    def _neutral_strategy(
        cls,
    ) -> dict[str, Any]:
        return {
            "status": "neutral",
            "active_goal_count": 0,
            "primary_goal": None,
            "target_metric": None,
            "trajectory": None,
            "urgency": 0.0,
            "production_priority": (
                cls.NEUTRAL_PRIORITY
            ),
            "exploration_bias": 0.5,
            "exploitation_bias": 0.5,
            "scheduler_interval_multiplier": 1.0,
            "rationale": (
                "No active production goal "
                "requires strategic adjustment."
            ),
        }

    @staticmethod
    def _rationale(
        trajectory: str,
    ) -> str:
        if trajectory == "behind":
            return (
                "Primary goal is behind trajectory; "
                "favor proven production patterns while "
                "keeping scheduler cadence unchanged."
            )

        if trajectory == "on_track":
            return (
                "Primary goal is on track; maintain a "
                "moderate preference for proven patterns."
            )

        return (
            "Primary goal is ahead of trajectory; allow "
            "more exploration while keeping production "
            "quality controls unchanged."
        )
