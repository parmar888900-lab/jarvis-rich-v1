import asyncio
from datetime import datetime, timedelta

from backend.models.goal import (
    GoalPeriod,
    GoalRecord,
    GoalStatus,
)
from backend.services.orchestration.goal_production_strategy_service import (
    GoalProductionStrategyService,
)


START = datetime(
    2026,
    8,
    30,
    12,
    0,
    0,
)

NOW = START + timedelta(
    days=3.5
)

DEADLINE = START + timedelta(
    days=7
)


def make_goal(
    *,
    goal_id,
    name,
    current_value,
    status=GoalStatus.ACTIVE,
):
    goal = GoalRecord(
        name=name,
        metric="views",
        target_value=100000,
        starting_value=0,
        current_value=current_value,
        period=GoalPeriod.WEEKLY,
        start_date=START,
        deadline=DEADLINE,
        status=status,
    )

    goal.id = goal_id

    return goal


class FakeGoalService:
    def __init__(
        self,
        goals,
    ):
        self.goals = goals
        self.calls = []

    async def list_goals(
        self,
        session,
        *,
        status=None,
        metric=None,
    ):
        self.calls.append(
            {
                "session": session,
                "status": status,
                "metric": metric,
            }
        )

        return [
            goal
            for goal in self.goals
            if (
                status is None
                or goal.status == status
            )
        ]


async def main():
    print(
        "======================================================"
    )
    print(
        "GOAL PRODUCTION STRATEGY SERVICE TEST"
    )
    print(
        "======================================================"
    )

    session = object()

    empty_goal_service = FakeGoalService(
        []
    )

    empty_service = (
        GoalProductionStrategyService(
            goal_service=empty_goal_service
        )
    )

    neutral = await empty_service.build(
        session,
        now=NOW,
    )

    assert neutral["status"] == "neutral"
    assert neutral["source_goal_count"] == 0
    assert neutral["evaluated_goal_count"] == 0
    assert neutral["active_goal_count"] == 0
    assert (
        neutral[
            "scheduler_interval_multiplier"
        ]
        == 1.0
    )

    assert len(
        empty_goal_service.calls
    ) == 1

    assert (
        empty_goal_service.calls[0][
            "status"
        ]
        == GoalStatus.ACTIVE
    )

    print(
        "PASS: no active goals produce "
        "neutral runtime strategy."
    )

    goals = [
        make_goal(
            goal_id="ahead",
            name="Ahead Goal",
            current_value=70000,
        ),
        make_goal(
            goal_id="behind",
            name="Behind Goal",
            current_value=25000,
        ),
        make_goal(
            goal_id="paused",
            name="Paused Goal",
            current_value=10000,
            status=GoalStatus.PAUSED,
        ),
    ]

    fake_goal_service = FakeGoalService(
        goals
    )

    service = (
        GoalProductionStrategyService(
            goal_service=fake_goal_service
        )
    )

    result = await service.build(
        session,
        now=NOW,
    )

    assert result["status"] == "goal_guided"

    assert result[
        "source_goal_count"
    ] == 2

    assert result[
        "evaluated_goal_count"
    ] == 2

    assert result[
        "active_goal_count"
    ] == 2

    assert (
        result["primary_goal"][
            "goal_id"
        ]
        == "behind"
    )

    assert (
        result["trajectory"]
        == "behind"
    )

    assert (
        result["target_metric"]
        == "views"
    )

    assert (
        result["production_priority"]
        > 50.0
    )

    assert (
        result["exploitation_bias"]
        > result["exploration_bias"]
    )

    assert (
        result[
            "scheduler_interval_multiplier"
        ]
        == 1.0
    )

    print(
        "PASS: real GoalEngine evaluations "
        "feed production strategy."
    )

    print(
        "PASS: inactive goals are excluded "
        "before strategy evaluation."
    )

    print(
        "PASS: behind active goal becomes "
        "the primary production objective."
    )

    print(
        "PASS: runtime strategy preserves "
        "scheduler cadence."
    )

    print()
    print(
        "STRATEGY"
    )
    print(
        "------------------------------------------------------"
    )
    print(
        "status:",
        result["status"],
    )
    print(
        "active_goal_count:",
        result["active_goal_count"],
    )
    print(
        "primary_goal:",
        result["primary_goal"]["name"],
    )
    print(
        "trajectory:",
        result["trajectory"],
    )
    print(
        "urgency:",
        result["urgency"],
    )
    print(
        "production_priority:",
        result["production_priority"],
    )
    print(
        "exploration_bias:",
        result["exploration_bias"],
    )
    print(
        "exploitation_bias:",
        result["exploitation_bias"],
    )
    print(
        "scheduler_interval_multiplier:",
        result[
            "scheduler_interval_multiplier"
        ],
    )

    print()
    print(
        "======================================================"
    )
    print(
        "GOAL PRODUCTION STRATEGY SERVICE TEST PASSED"
    )
    print(
        "======================================================"
    )


asyncio.run(
    main()
)
