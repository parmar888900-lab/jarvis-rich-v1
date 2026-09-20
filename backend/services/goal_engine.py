"""Target and progress calculations for Jarvis goals."""

from datetime import datetime

from backend.models.goal import (
    GoalRecord,
    GoalStatus,
)


class GoalEngine:
    """Calculate goal progress and trajectory."""

    ON_TRACK_TOLERANCE = 0.05

    def evaluate(
        self,
        goal: GoalRecord,
        now: datetime | None = None,
    ) -> dict:

        now = now or datetime.now()

        start = goal.start_date
        deadline = goal.deadline

        if deadline <= start:
            raise ValueError(
                "Goal deadline must be after start_date."
            )

        target_gain = (
            goal.target_value
            - goal.starting_value
        )

        actual_gain = (
            goal.current_value
            - goal.starting_value
        )

        if target_gain <= 0:
            raise ValueError(
                "target_value must be greater "
                "than starting_value."
            )

        total_seconds = (
            deadline - start
        ).total_seconds()

        elapsed_seconds = (
            now - start
        ).total_seconds()

        time_progress = max(
            0.0,
            min(
                elapsed_seconds
                / total_seconds,
                1.0,
            ),
        )

        progress = max(
            0.0,
            actual_gain / target_gain,
        )

        expected_gain = (
            target_gain
            * time_progress
        )

        expected_value = (
            goal.starting_value
            + expected_gain
        )

        remaining_value = max(
            0.0,
            goal.target_value
            - goal.current_value,
        )

        remaining_seconds = max(
            0.0,
            (
                deadline - now
            ).total_seconds(),
        )

        remaining_days = (
            remaining_seconds
            / 86400
        )

        if remaining_value <= 0:
            required_daily_rate = 0.0
        elif remaining_days > 0:
            required_daily_rate = (
                remaining_value
                / remaining_days
            )
        else:
            required_daily_rate = None

        if time_progress < 0.01:
            pace_ratio = None
        else:
            pace_ratio = (
                progress
                / time_progress
            )

        trajectory = self._trajectory(
            progress=progress,
            time_progress=time_progress,
            completed=(
                goal.current_value
                >= goal.target_value
            ),
            expired=(
                now >= deadline
            ),
        )

        effective_status = (
            self._effective_status(
                goal=goal,
                now=now,
            )
        )

        return {
            "goal_id": goal.id,
            "name": goal.name,
            "metric": goal.metric,
            "target_value": goal.target_value,
            "starting_value": goal.starting_value,
            "current_value": goal.current_value,
            "progress_percent": round(
                progress * 100,
                2,
            ),
            "time_progress_percent": round(
                time_progress * 100,
                2,
            ),
            "expected_value_now": round(
                expected_value,
                2,
            ),
            "remaining_value": round(
                remaining_value,
                2,
            ),
            "remaining_days": round(
                remaining_days,
                2,
            ),
            "required_daily_rate": (
                round(
                    required_daily_rate,
                    2,
                )
                if required_daily_rate
                is not None
                else None
            ),
            "pace_ratio": (
                round(
                    pace_ratio,
                    3,
                )
                if pace_ratio
                is not None
                else None
            ),
            "trajectory": trajectory,
            "status": effective_status.value,
        }

    def _trajectory(
        self,
        progress: float,
        time_progress: float,
        completed: bool,
        expired: bool,
    ) -> str:

        if completed:
            return "completed"

        if expired:
            return "missed"

        difference = (
            progress
            - time_progress
        )

        if (
            difference
            > self.ON_TRACK_TOLERANCE
        ):
            return "ahead"

        if (
            difference
            < -self.ON_TRACK_TOLERANCE
        ):
            return "behind"

        return "on_track"

    @staticmethod
    def _effective_status(
        goal: GoalRecord,
        now: datetime,
    ) -> GoalStatus:

        if goal.status == GoalStatus.PAUSED:
            return GoalStatus.PAUSED

        if (
            goal.current_value
            >= goal.target_value
        ):
            return GoalStatus.COMPLETED

        if now >= goal.deadline:
            return GoalStatus.FAILED

        return goal.status

