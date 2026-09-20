from backend.services.orchestration.daily_format_rotator import (
    DailyFormatRotator,
)
from backend.services.intelligence.genre_topic_selector import (
    GenreTopicSelector,
)


rotator = DailyFormatRotator()

selector = GenreTopicSelector(
    history_path=(
        "generated/state/"
        "topic_history_test.json"
    )
)

slots = rotator.build_slots(
    cursor=0,
    daily_target=4,
)

print()
print("========== DAILY PRODUCTION PLAN ==========")

for slot in slots:

    topic = selector.select(
        format_name=slot.format_name,
    )

    print(
        f"SLOT {slot.slot_index}",
        "|",
        slot.format_name,
        "|",
        topic.topic,
        "| score:",
        topic.final_score,
    )

    selector.mark_used(
        topic
    )

print()
print("========== SECOND PASS ==========")

for slot in slots:

    topic = selector.select(
        format_name=slot.format_name,
    )

    print(
        slot.format_name,
        "->",
        topic.topic,
    )
