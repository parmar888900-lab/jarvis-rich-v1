from backend.services.intelligence.content_format_classifier import (
    ContentFormatClassifier,
)
from backend.services.video.visual_beat_planner import (
    VisualBeatPlanner,
)
from backend.models.generated_content import GeneratedContent


topic = (
    "Why train wheels are shaped "
    "differently from car wheels"
)

genre = "science_engineering"

content = GeneratedContent(
    title=topic,
    hashtags=[
        "#engineering",
        "#trains",
        "#shorts",
    ],
    script_lines=[
        (
            "Train wheels use a carefully machined profile "
            "designed to interact with railway tracks."
        ),
        (
            "The wheel and rail geometry helps guide the "
            "vehicle while carrying extremely heavy loads."
        ),
        (
            "Worn or incorrectly profiled wheels can increase "
            "rolling resistance and reduce efficiency."
        ),
        (
            "That is why railway wheels are regularly inspected "
            "and machined to controlled profiles."
        ),
    ],
)

classifier = ContentFormatClassifier()

decision = classifier.classify(
    topic=topic,
    genre=genre,
)

print("FORMAT:", decision.format_name)
print(
    "DURATION:",
    decision.target_duration_min,
    "-",
    decision.target_duration_max,
)
print("PACING:", decision.pacing)

planner = VisualBeatPlanner()

beats = planner.plan(
    content=content,
    topic=topic,
    genre=genre,
    format_name=decision.format_name,
)

print()
print("BEATS:", len(beats))

for beat in beats:
    print(
        beat.beat_id,
        "|",
        beat.purpose,
        "|",
        beat.target_duration,
        "|",
        beat.search_query,
    )
