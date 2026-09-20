"""Runtime service for goal-aware production strategy."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.goal import GoalStatus
from backend.services.goal_engine import GoalEngine
from backend.services.goal_service import GoalService
from backend.services.orchestration.goal_production_strategy import (
    GoalProductionStrategy,
)


class GoalProductionStrategyService:
    """Load active goals and convert them into production guidance."""

    def __init__(
        self,
        *,
        goal_service: GoalService | None = None,
        goal_engine: GoalEngine | None = None,
        strategy: GoalProductionStrategy | None = None,
    ) -> None:

        self.goal_service = (
            goal_service
            if goal_service is not None
            else GoalService()
        )

        self.goal_engine = (
            goal_engine
            if goal_engine is not None
            else GoalEngine()
        )

        self.strategy = (
            strategy
            if strategy is not None
            else GoalProductionStrategy()
        )

    async def build(
        self,
        session: AsyncSession,
        *,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        """Build production strategy from currently active goals."""

        goals = await self.goal_service.list_goals(
            session,
            status=GoalStatus.ACTIVE,
        )

        evaluations = [
            self.goal_engine.evaluate(
                goal,
                now=now,
            )
            for goal in goals
        ]

        result = self.strategy.build(
            evaluations
        )

        return {
            **result,
            "source_goal_count": len(goals),
            "evaluated_goal_count": len(
                evaluations
            ),
        }
