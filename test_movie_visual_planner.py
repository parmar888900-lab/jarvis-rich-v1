from backend.models.generated_content import GeneratedContent
from backend.services.storyboard.movie_visual_beat_planner import (
    MovieVisualBeatPlanner,
)


content = GeneratedContent(
    title=(
        "Doctor Strange's Mind-Bending "
        "Mirror Dimension Scenes"
    ),
    hashtags=[
        "#DoctorStrange",
        "#VisualEffects",
        "#Marvel",
    ],
    script_lines=[
        (
            "Doctor Strange's mirror dimension chase "
            "is a mind-bending spectacle, blending "
            "mysticism with visual effects."
        ),
        (
            "Director Scott Derrickson wanted action "
            "built around different dimensions instead "
            "of conventional superhero attacks."
        ),
        (
            "The production used extensive visual effects "
            "to create the surreal dimensional action."
        ),
        (
            "That approach gave the film a visually "
            "different style of superhero action."
        ),
    ],
    metadata={
        "content_format": (
            "famous_movie_commentary"
        ),
        "movie_title": "Doctor Strange",
        "evidence_ids": [
            ["E3", "E4"],
            ["E3"],
            ["E3", "E4"],
            ["E3"],
        ],
    },
)

planner = MovieVisualBeatPlanner()

beats = planner.plan(
    content=content,
    movie_title="Doctor Strange",
    topic=(
        "Why Doctor Strange's mirror "
        "dimension scenes work so well"
    ),
)

print()
print("========== MOVIE VISUAL PLAN ==========")
print("BEATS:", len(beats))

total = 0.0

for beat in beats:
    total += beat.target_duration

    print(
        beat.beat_id,
        "|",
        beat.purpose,
        "|",
        beat.target_duration,
        "|",
        beat.visual_query,
        "|",
        beat.evidence_ids,
    )

print()
print(
    "PLANNED VISUAL TIME:",
    round(total, 2),
)
