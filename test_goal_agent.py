import asyncio
from datetime import datetime, timedelta

from backend.database import engine
from backend.services.agent_handlers.goal import GoalAgentHandler


async def main():
    handler = GoalAgentHandler()

    start = datetime.now()
    deadline = start + timedelta(days=7)

    created = await handler.execute(
        task="create_goal",
        command_id="goal-test-create",
        name="Goal Agent Integration Test",
        metric="views",
        target_value=100000,
        starting_value=0,
        current_value=20000,
        period="weekly",
        start_date=start,
        deadline=deadline,
    )

    print("CREATE:")
    print(created)

    goal_id = created["goal"]["goal_id"]

    status = await handler.execute(
        task="get_goal_status",
        command_id="goal-test-status",
        goal_id=goal_id,
    )

    print()
    print("STATUS:")
    print(status)

    updated = await handler.execute(
        task="update_goal",
        command_id="goal-test-update",
        goal_id=goal_id,
        current_value=60000,
    )

    print()
    print("UPDATE:")
    print(updated)

    paused = await handler.execute(
        task="pause_goal",
        command_id="goal-test-pause",
        goal_id=goal_id,
    )

    print()
    print("PAUSE:")
    print(paused)

    resumed = await handler.execute(
        task="resume_goal",
        command_id="goal-test-resume",
        goal_id=goal_id,
    )

    print()
    print("RESUME:")
    print(resumed)

    listed = await handler.execute(
        task="list_goals",
        command_id="goal-test-list",
        metric="views",
    )

    print()
    print("LIST COUNT:")
    print(listed["count"])

    assert created["status"] == "created"
    assert status["goal"]["goal_id"] == goal_id
    assert updated["goal"]["current_value"] == 60000
    assert paused["goal"]["status"] == "paused"
    assert resumed["goal"]["status"] == "active"
    assert listed["count"] >= 1

    print()
    print(
        "PASS: Goal agent full lifecycle works."
    )

    await engine.dispose()


asyncio.run(main())
