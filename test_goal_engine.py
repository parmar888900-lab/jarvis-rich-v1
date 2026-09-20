from datetime import datetime, timedelta

from backend.models.goal import (
    GoalPeriod,
    GoalRecord,
    GoalStatus,
)
from backend.services.goal_engine import GoalEngine


start = datetime(2026, 8, 24, 12, 0, 0)
deadline = start + timedelta(days=7)
now = start + timedelta(days=3.5)

engine = GoalEngine()


def make_goal(
    name: str,
    current: float,
) -> GoalRecord:
    return GoalRecord(
        name=name,
        metric="views",
        target_value=100000,
        starting_value=0,
        current_value=current,
        period=GoalPeriod.WEEKLY,
        start_date=start,
        deadline=deadline,
        status=GoalStatus.ACTIVE,
    )


tests = [
    make_goal(
        "Ahead Goal",
        70000,
    ),
    make_goal(
        "On Track Goal",
        50000,
    ),
    make_goal(
        "Behind Goal",
        25000,
    ),
    make_goal(
        "Completed Goal",
        100000,
    ),
]

for goal in tests:
    result = engine.evaluate(
        goal,
        now=now,
    )

    print()
    print(goal.name)
    print(
        "Progress:",
        result["progress_percent"],
    )
    print(
        "Time:",
        result["time_progress_percent"],
    )
    print(
        "Trajectory:",
        result["trajectory"],
    )
    print(
        "Required/day:",
        result["required_daily_rate"],
    )
    print(
        "Status:",
        result["status"],
    )


assert engine.evaluate(
    tests[0],
    now=now,
)["trajectory"] == "ahead"

assert engine.evaluate(
    tests[1],
    now=now,
)["trajectory"] == "on_track"

assert engine.evaluate(
    tests[2],
    now=now,
)["trajectory"] == "behind"

assert engine.evaluate(
    tests[3],
    now=now,
)["trajectory"] == "completed"

print()
print(
    "PASS: Goal Engine trajectory "
    "calculations are correct."
)
