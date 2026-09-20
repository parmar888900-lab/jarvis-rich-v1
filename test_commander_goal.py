import asyncio
import json
from datetime import datetime, timedelta

from sqlalchemy import delete, select

from backend.database import async_session, engine
from backend.models.command import (
    CommandRecord,
    CommandSubmitRequest,
)
from backend.models.goal import GoalRecord
from backend.services.commander import Commander


async def main():
    commander = Commander()

    start = datetime.now()
    deadline = start + timedelta(days=7)

    payload = CommandSubmitRequest(
        agent="goal",
        task="create_goal",
        parameters={
            "name": "Commander Goal Test",
            "metric": "views",
            "target_value": 100000,
            "starting_value": 0,
            "current_value": 25000,
            "period": "weekly",
            "start_date": start.isoformat(),
            "deadline": deadline.isoformat(),
        },
    )

    async with async_session() as session:
        response = await commander.receive(
            session,
            payload,
        )

        print("COMMAND RESPONSE:")
        print(response.model_dump())

        command = await session.get(
            CommandRecord,
            response.command_id,
        )

        assert command is not None

        print()
        print("COMMAND STATUS:")
        print(command.status.value)

        result = json.loads(command.result)

        print()
        print("COMMAND RESULT:")
        print(result)

        goal_id = result["goal"]["goal_id"]

        goal = await session.get(
            GoalRecord,
            goal_id,
        )

        assert goal is not None

        print()
        print("GOAL ID:", goal.id)
        print("GOAL NAME:", goal.name)
        print("CURRENT VALUE:", goal.current_value)
        print(
            "TARGET VALUE:",
            goal.target_value,
        )

        assert command.status.value == "completed"
        assert result["agent"] == "goal"
        assert result["task"] == "create_goal"
        assert result["status"] == "created"
        assert goal.current_value == 25000
        assert goal.target_value == 100000

        print()
        print(
            "PASS: Commander -> Goal Agent -> "
            "GoalService integration works."
        )

        # Clean up both test records.
        await session.execute(
            delete(GoalRecord).where(
                GoalRecord.id == goal_id
            )
        )

        await session.execute(
            delete(CommandRecord).where(
                CommandRecord.id
                == response.command_id
            )
        )

        await session.commit()

        remaining_goal = await session.scalar(
            select(GoalRecord).where(
                GoalRecord.id == goal_id
            )
        )

        remaining_command = await session.scalar(
            select(CommandRecord).where(
                CommandRecord.id
                == response.command_id
            )
        )

        assert remaining_goal is None
        assert remaining_command is None

        print(
            "PASS: integration test records "
            "cleaned up."
        )

    await engine.dispose()


asyncio.run(main())
