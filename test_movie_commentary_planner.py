from backend.services.intelligence.content_format_classifier import (
    ContentFormatClassifier,
)
from backend.services.video.movie_commentary_planner import (
    MovieCommentaryPlanner,
)


topic = (
    "Why Doctor Strange's mirror dimension "
    "scenes work so well"
)

genre = "famous_movie_commentary"

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
print(
    "RIGHTS GATE:",
    decision.rights_gate_required,
)
print(
    "NARRATION:",
    decision.narration_mode,
)

planner = MovieCommentaryPlanner()

beats = planner.plan(
    movie_title="Doctor Strange",
    topic=topic,
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
        beat.visual_goal,
    )
