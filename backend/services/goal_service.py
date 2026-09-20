"""Persistence service for Jarvis goals."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.goal import (
    GoalPeriod,
    GoalRecord,
    GoalStatus,
)


class GoalService:
    """Create, retrieve, update, and manage goals."""

    async def create_goal(
        self,
        session: AsyncSession,
        *,
        name: str,
        metric: str,
        target_value: float,
        start_date: datetime,
        deadline: datetime,
        starting_value: float = 0.0,
        current_value: float | None = None,
        period: GoalPeriod = GoalPeriod.CUSTOM,
    ) -> GoalRecord:

        name = name.strip()
        metric = metric.strip().lower()

        if not name:
            raise ValueError(
                "Goal name cannot be empty."
            )

        if not metric:
            raise ValueError(
                "Goal metric cannot be empty."
            )

        if deadline <= start_date:
            raise ValueError(
                "Goal deadline must be after start_date."
            )

        if target_value <= starting_value:
            raise ValueError(
                "target_value must be greater "
                "than starting_value."
            )

        if current_value is None:
            current_value = starting_value

        goal = GoalRecord(
            name=name,
            metric=metric,
            target_value=float(
                target_value
            ),
            starting_value=float(
                starting_value
            ),
            current_value=float(
                current_value
            ),
            period=period,
            start_date=start_date,
            deadline=deadline,
            status=GoalStatus.ACTIVE,
        )

        session.add(
            goal
        )

        await session.commit()
        await session.refresh(
            goal
        )

        return goal

    async def get_goal(
        self,
        session: AsyncSession,
        goal_id: str,
    ) -> GoalRecord | None:

        return await session.get(
            GoalRecord,
            goal_id,
        )

    async def list_goals(
        self,
        session: AsyncSession,
        *,
        status: GoalStatus | None = None,
        metric: str | None = None,
    ) -> list[GoalRecord]:

        statement = select(
            GoalRecord
        )

        if status is not None:
            statement = statement.where(
                GoalRecord.status
                == status
            )

        if metric:
            statement = statement.where(
                GoalRecord.metric
                == metric.strip().lower()
            )

        statement = statement.order_by(
            GoalRecord.created_at.desc()
        )

        result = await session.execute(
            statement
        )

        return list(
            result.scalars().all()
        )

    async def update_value(
        self,
        session: AsyncSession,
        goal_id: str,
        current_value: float,
    ) -> GoalRecord:

        goal = await self.get_goal(
            session,
            goal_id,
        )

        if goal is None:
            raise ValueError(
                f"Goal not found: {goal_id}"
            )

        goal.current_value = float(
            current_value
        )

        if (
            goal.current_value
            >= goal.target_value
        ):
            goal.status = (
                GoalStatus.COMPLETED
            )
        elif (
            goal.status
            == GoalStatus.COMPLETED
        ):
            goal.status = (
                GoalStatus.ACTIVE
            )

        await session.commit()
        await session.refresh(
            goal
        )

        return goal

    async def pause_goal(
        self,
        session: AsyncSession,
        goal_id: str,
    ) -> GoalRecord:

        goal = await self._require_goal(
            session,
            goal_id,
        )

        if (
            goal.status
            == GoalStatus.COMPLETED
        ):
            raise ValueError(
                "Completed goals cannot be paused."
            )

        goal.status = GoalStatus.PAUSED

        await session.commit()
        await session.refresh(
            goal
        )

        return goal

    async def resume_goal(
        self,
        session: AsyncSession,
        goal_id: str,
    ) -> GoalRecord:

        goal = await self._require_goal(
            session,
            goal_id,
        )

        if (
            goal.status
            != GoalStatus.PAUSED
        ):
            raise ValueError(
                "Only paused goals can be resumed."
            )

        goal.status = GoalStatus.ACTIVE

        await session.commit()
        await session.refresh(
            goal
        )

        return goal

    async def _require_goal(
        self,
        session: AsyncSession,
        goal_id: str,
    ) -> GoalRecord:

        goal = await self.get_goal(
            session,
            goal_id,
        )

        if goal is None:
            raise ValueError(
                f"Goal not found: {goal_id}"
            )

        return goal
