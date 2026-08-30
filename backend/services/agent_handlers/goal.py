"""Goal agent handler for Jarvis target management."""

from datetime import datetime

from backend.database import async_session
from backend.models.goal import (
    GoalPeriod,
    GoalStatus,
)
from backend.services.agent_handlers.base import BaseAgentHandler
from backend.services.goal_engine import GoalEngine
from backend.services.goal_service import GoalService


class GoalAgentHandler(BaseAgentHandler):
    name = "goal"

    supported_tasks = frozenset(
        {
            "create_goal",
            "get_goal_status",
            "update_goal",
            "list_goals",
            "pause_goal",
            "resume_goal",
        }
    )

    def __init__(self) -> None:
        self.service = GoalService()
        self.engine = GoalEngine()

    async def execute(
        self,
        task: str,
        command_id: str,
        **kwargs,
    ) -> dict:

        handlers = {
            "create_goal": self._create_goal,
            "get_goal_status": self._get_goal_status,
            "update_goal": self._update_goal,
            "list_goals": self._list_goals,
            "pause_goal": self._pause_goal,
            "resume_goal": self._resume_goal,
        }

        handler = handlers.get(task)

        if handler is None:
            raise ValueError(
                f"Unsupported goal task: {task}"
            )

        result = await handler(**kwargs)

        return {
            "agent": self.name,
            "task": task,
            "command_id": command_id,
            **result,
        }

    async def _create_goal(
        self,
        *,
        name: str,
        metric: str,
        target_value: float,
        start_date: datetime,
        deadline: datetime,
        starting_value: float = 0.0,
        current_value: float | None = None,
        period: str = "custom",
        **_,
    ) -> dict:

        try:
            goal_period = GoalPeriod(
                period.lower()
            )
        except ValueError as exc:
            raise ValueError(
                f"Invalid goal period: {period}"
            ) from exc

        async with async_session() as session:
            goal = await self.service.create_goal(
                session,
                name=name,
                metric=metric,
                target_value=target_value,
                starting_value=starting_value,
                current_value=current_value,
                period=goal_period,
                start_date=start_date,
                deadline=deadline,
            )

            evaluation = self.engine.evaluate(
                goal
            )

            return {
                "status": "created",
                "goal": evaluation,
            }

    async def _get_goal_status(
        self,
        *,
        goal_id: str,
        **_,
    ) -> dict:

        async with async_session() as session:
            goal = await self.service.get_goal(
                session,
                goal_id,
            )

            if goal is None:
                raise ValueError(
                    f"Goal not found: {goal_id}"
                )

            return {
                "status": "success",
                "goal": self.engine.evaluate(
                    goal
                ),
            }

    async def _update_goal(
        self,
        *,
        goal_id: str,
        current_value: float,
        **_,
    ) -> dict:

        async with async_session() as session:
            goal = await self.service.update_value(
                session,
                goal_id,
                current_value,
            )

            return {
                "status": "updated",
                "goal": self.engine.evaluate(
                    goal
                ),
            }

    async def _list_goals(
        self,
        *,
        status: str | None = None,
        metric: str | None = None,
        **_,
    ) -> dict:

        parsed_status = None

        if status is not None:
            try:
                parsed_status = GoalStatus(
                    status.lower()
                )
            except ValueError as exc:
                raise ValueError(
                    f"Invalid goal status: {status}"
                ) from exc

        async with async_session() as session:
            goals = await self.service.list_goals(
                session,
                status=parsed_status,
                metric=metric,
            )

            return {
                "status": "success",
                "count": len(goals),
                "goals": [
                    self.engine.evaluate(goal)
                    for goal in goals
                ],
            }

    async def _pause_goal(
        self,
        *,
        goal_id: str,
        **_,
    ) -> dict:

        async with async_session() as session:
            goal = await self.service.pause_goal(
                session,
                goal_id,
            )

            return {
                "status": "paused",
                "goal": self.engine.evaluate(
                    goal
                ),
            }

    async def _resume_goal(
        self,
        *,
        goal_id: str,
        **_,
    ) -> dict:

        async with async_session() as session:
            goal = await self.service.resume_goal(
                session,
                goal_id,
            )

            return {
                "status": "resumed",
                "goal": self.engine.evaluate(
                    goal
                ),
            }
