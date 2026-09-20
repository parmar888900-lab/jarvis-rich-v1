import asyncio
from datetime import datetime, timedelta

from backend.database import (
    async_session,
    engine,
)
from backend.models.goal import GoalPeriod
from backend.services.goal_engine import GoalEngine
from backend.services.goal_service import GoalService


async def main():

    service = GoalService()
    evaluator = GoalEngine()

    start = datetime.now()
    deadline = (
        start
        + timedelta(days=7)
    )

    async with async_session() as session:

        goal = await service.create_goal(
            session,
            name="Jarvis Goal Engine Test",
            metric="views",
            target_value=100000,
            starting_value=0,
            current_value=40000,
            period=GoalPeriod.WEEKLY,
            start_date=start,
            deadline=deadline,
        )

        print(
            "GOAL ID:",
            goal.id,
        )

        print(
            "NAME:",
            goal.name,
        )

        print(
            "VALUE:",
            goal.current_value,
            "/",
            goal.target_value,
        )

        evaluation = evaluator.evaluate(
            goal,
            now=start
            + timedelta(days=3.5),
        )

        print()
        print("EVALUATION")
        print(
            "Progress:",
            evaluation[
                "progress_percent"
            ],
        )
        print(
            "Time progress:",
            evaluation[
                "time_progress_percent"
            ],
        )
        print(
            "Trajectory:",
            evaluation[
                "trajectory"
            ],
        )
        print(
            "Expected now:",
            evaluation[
                "expected_value_now"
            ],
        )
        print(
            "Required/day:",
            evaluation[
                "required_daily_rate"
            ],
        )
        print(
            "Status:",
            evaluation[
                "status"
            ],
        )

        fetched = await service.get_goal(
            session,
            goal.id,
        )

        assert fetched is not None
        assert fetched.id == goal.id

        print()
        print(
            "PASS: Jarvis real database "
            "goal persistence works."
        )

    await engine.dispose()


asyncio.run(main())
