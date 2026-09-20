import asyncio
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy.ext.asyncio import (
    async_sessionmaker,
    create_async_engine,
)

from backend.database import Base
from backend.models.goal import (
    GoalPeriod,
    GoalStatus,
)
from backend.services.goal_engine import GoalEngine
from backend.services.goal_service import GoalService


async def main():

    db_path = Path(
        "goal_engine_test.db"
    )

    if db_path.exists():
        db_path.unlink()

    engine = create_async_engine(
        "sqlite+aiosqlite:///goal_engine_test.db"
    )

    Session = async_sessionmaker(
        engine,
        expire_on_commit=False,
    )

    async with engine.begin() as conn:
        await conn.run_sync(
            Base.metadata.create_all
        )

    service = GoalService()
    evaluator = GoalEngine()

    start = datetime(
        2026,
        8,
        29,
        12,
        0,
        0,
    )

    deadline = (
        start
        + timedelta(days=7)
    )

    async with Session() as session:

        goal = await service.create_goal(
            session,
            name="Weekly Views",
            metric="views",
            target_value=100000,
            starting_value=0,
            current_value=0,
            period=GoalPeriod.WEEKLY,
            start_date=start,
            deadline=deadline,
        )

        print(
            "CREATED:",
            goal.name,
            goal.metric,
            goal.status.value,
        )

        fetched = await service.get_goal(
            session,
            goal.id,
        )

        assert fetched is not None
        assert fetched.id == goal.id

        updated = await service.update_value(
            session,
            goal.id,
            60000,
        )

        print(
            "UPDATED VALUE:",
            updated.current_value,
        )

        evaluation = evaluator.evaluate(
            updated,
            now=start
            + timedelta(days=3.5),
        )

        print(
            "TRAJECTORY:",
            evaluation["trajectory"],
        )
        print(
            "PROGRESS:",
            evaluation[
                "progress_percent"
            ],
        )

        goals = await service.list_goals(
            session,
            status=GoalStatus.ACTIVE,
        )

        print(
            "ACTIVE GOALS:",
            len(goals),
        )

        assert len(goals) == 1
        assert (
            evaluation[
                "trajectory"
            ]
            == "ahead"
        )

        completed = (
            await service.update_value(
                session,
                goal.id,
                100000,
            )
        )

        print(
            "FINAL STATUS:",
            completed.status.value,
        )

        assert (
            completed.status
            == GoalStatus.COMPLETED
        )

    await engine.dispose()

    if db_path.exists():
        db_path.unlink()

    print()
    print(
        "PASS: Goal persistence "
        "and evaluation work together."
    )


asyncio.run(main())
