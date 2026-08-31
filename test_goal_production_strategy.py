from backend.services.orchestration.goal_production_strategy import (
    GoalProductionStrategy,
)


strategy = GoalProductionStrategy()


def goal(
    *,
    goal_id,
    name,
    trajectory,
    remaining_days,
    status="active",
    metric="views",
):
    return {
        "goal_id": goal_id,
        "name": name,
        "metric": metric,
        "target_value": 100000,
        "starting_value": 0,
        "current_value": 25000,
        "progress_percent": 25.0,
        "time_progress_percent": 50.0,
        "expected_value_now": 50000,
        "remaining_value": 75000,
        "remaining_days": remaining_days,
        "required_daily_rate": 15000,
        "pace_ratio": 0.5,
        "trajectory": trajectory,
        "status": status,
    }


print(
    "======================================================"
)
print(
    "GOAL PRODUCTION STRATEGY TEST"
)
print(
    "======================================================"
)


neutral = strategy.build([])

assert neutral["status"] == "neutral"
assert neutral["active_goal_count"] == 0
assert neutral["primary_goal"] is None
assert neutral["production_priority"] == 50.0
assert neutral["exploration_bias"] == 0.5
assert neutral["exploitation_bias"] == 0.5
assert (
    neutral["scheduler_interval_multiplier"]
    == 1.0
)

print(
    "PASS: no active goals produce "
    "neutral strategy."
)


paused = strategy.build(
    [
        goal(
            goal_id="paused",
            name="Paused Goal",
            trajectory="behind",
            remaining_days=1,
            status="paused",
        )
    ]
)

assert paused["status"] == "neutral"

print(
    "PASS: paused goals cannot influence "
    "production strategy."
)


completed = strategy.build(
    [
        goal(
            goal_id="complete",
            name="Completed Goal",
            trajectory="completed",
            remaining_days=0,
            status="completed",
        )
    ]
)

assert completed["status"] == "neutral"

print(
    "PASS: completed goals cannot influence "
    "production strategy."
)


ahead = strategy.build(
    [
        goal(
            goal_id="ahead",
            name="Ahead Goal",
            trajectory="ahead",
            remaining_days=5,
        )
    ]
)

on_track = strategy.build(
    [
        goal(
            goal_id="track",
            name="On Track Goal",
            trajectory="on_track",
            remaining_days=5,
        )
    ]
)

behind = strategy.build(
    [
        goal(
            goal_id="behind",
            name="Behind Goal",
            trajectory="behind",
            remaining_days=5,
        )
    ]
)

assert (
    ahead["production_priority"]
    < on_track["production_priority"]
    < behind["production_priority"]
)

assert (
    ahead["exploitation_bias"]
    < on_track["exploitation_bias"]
    < behind["exploitation_bias"]
)

print(
    "PASS: behind trajectory creates greater "
    "strategic pressure than on-track/ahead."
)


early_behind = strategy.build(
    [
        goal(
            goal_id="early",
            name="Early Behind Goal",
            trajectory="behind",
            remaining_days=6,
        )
    ]
)

urgent_behind = strategy.build(
    [
        goal(
            goal_id="urgent",
            name="Urgent Behind Goal",
            trajectory="behind",
            remaining_days=1,
        )
    ]
)

assert (
    urgent_behind["urgency"]
    > early_behind["urgency"]
)

assert (
    urgent_behind["production_priority"]
    > early_behind["production_priority"]
)

assert (
    urgent_behind["exploitation_bias"]
    > early_behind["exploitation_bias"]
)

print(
    "PASS: deadline proximity increases bounded "
    "strategic urgency."
)


multiple = strategy.build(
    [
        goal(
            goal_id="ahead",
            name="Ahead Goal",
            trajectory="ahead",
            remaining_days=1,
        ),
        goal(
            goal_id="behind",
            name="Behind Goal",
            trajectory="behind",
            remaining_days=4,
        ),
        goal(
            goal_id="track",
            name="On Track Goal",
            trajectory="on_track",
            remaining_days=1,
        ),
    ]
)

assert multiple["active_goal_count"] == 3
assert (
    multiple["primary_goal"]["goal_id"]
    == "behind"
)
assert multiple["trajectory"] == "behind"

print(
    "PASS: highest-pressure active goal becomes "
    "the primary production goal."
)


same_trajectory = strategy.build(
    [
        goal(
            goal_id="later",
            name="Later Behind Goal",
            trajectory="behind",
            remaining_days=6,
        ),
        goal(
            goal_id="sooner",
            name="Sooner Behind Goal",
            trajectory="behind",
            remaining_days=1,
        ),
    ]
)

assert (
    same_trajectory["primary_goal"]["goal_id"]
    == "sooner"
)

print(
    "PASS: urgency breaks ties between goals "
    "with the same trajectory."
)


for result in (
    ahead,
    on_track,
    behind,
    urgent_behind,
    multiple,
):
    assert (
        0.0
        <= result["production_priority"]
        <= 100.0
    )

    assert (
        0.0
        <= result["exploration_bias"]
        <= 1.0
    )

    assert (
        0.0
        <= result["exploitation_bias"]
        <= 1.0
    )

    assert round(
        result["exploration_bias"]
        + result["exploitation_bias"],
        3,
    ) == 1.0

    assert (
        result["scheduler_interval_multiplier"]
        == 1.0
    )

print(
    "PASS: all strategy outputs remain bounded."
)

print(
    "PASS: strategy cannot silently alter "
    "scheduler cadence."
)

print()
print(
    "======================================================"
)
print(
    "GOAL PRODUCTION STRATEGY TEST PASSED"
)
print(
    "======================================================"
)
