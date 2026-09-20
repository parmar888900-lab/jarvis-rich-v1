import asyncio

from sqlalchemy import delete

from backend.database import async_session, engine
from backend.models.goal import GoalRecord


async def main():
    goal_id = "bf7444a2-cee8-49c8-9b62-636df93afd44"

    async with async_session() as session:
        result = await session.execute(
            delete(GoalRecord).where(
                GoalRecord.id == goal_id
            )
        )

        await session.commit()

        print(
            "DELETED ROWS:",
            result.rowcount,
        )

    await engine.dispose()

    print(
        "PASS: test goal removed "
        "from Jarvis database."
    )


asyncio.run(main())
