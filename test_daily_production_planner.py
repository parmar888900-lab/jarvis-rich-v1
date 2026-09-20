from pathlib import Path

from backend.services.orchestration.daily_production_planner import (
    DailyProductionPlanner,
)


state = Path(
    "generated/state/"
    "daily_production_state_test.json"
)

history = Path(
    "generated/state/"
    "daily_topic_history_test.json"
)

for path in (
    state,
    history,
):
    if path.exists():
        path.unlink()


planner = DailyProductionPlanner(
    state_path=state,
    history_path=history,
)

print()
print(
    "========== DAY 1 =========="
)

day1 = planner.build_plan(
    daily_target=4
)

for item in day1:

    print(
        item.slot_index,
        "|",
        item.format_name,
        "|",
        item.topic,
        "|",
        item.topic_score,
    )


print()
print(
    "========== DAY 2 =========="
)

day2 = planner.build_plan(
    daily_target=4
)

for item in day2:

    print(
        item.slot_index,
        "|",
        item.format_name,
        "|",
        item.topic,
        "|",
        item.topic_score,
    )


all_topics = [
    item.topic.lower()
    for item in (
        day1 + day2
    )
]

print()
print(
    "UNIQUE TOPICS:",
    len(
        set(all_topics)
    ),
    "/",
    len(all_topics),
)
