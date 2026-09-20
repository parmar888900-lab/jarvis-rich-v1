import asyncio

from backend.models.generated_content import GeneratedContent
from backend.services.storyboard.movie_visual_beat_planner import (
    MovieVisualBeatPlanner,
)
from backend.services.video.movie_media_resolver import (
    MovieMediaResolver,
)
from backend.services.video.visual_quality_validator import (
    VisualQualityValidator,
)


async def main():

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
            "content_format": "famous_movie_commentary",
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

    resolver = MovieMediaResolver()

    resolved = await resolver.resolve(
        beats=beats,
        content_id="visual-quality-calibration-001",
        movie_title="Doctor Strange",
    )

    validator = VisualQualityValidator()

    print()
    print(
        "========== VISUAL QUALITY CALIBRATION =========="
    )

    failures = []

    for item in resolved:

        if item.asset is None:

            print(
                item.beat_id,
                "| UNRESOLVED"
            )

            continue

        result = validator.validate(
            asset=item.asset,
        )

        averages = result.get(
            "averages",
            {},
        )

        print(
            item.beat_id,
            "|",
            "PASS"
            if result["valid"]
            else "FAIL",
            "| bright:",
            averages.get(
                "brightness"
            ),
            "| contrast:",
            averages.get(
                "contrast"
            ),
            "| dark:",
            averages.get(
                "dark_ratio"
            ),
            "| edge:",
            averages.get(
                "edge_activity"
            ),
            "| usable:",
            result.get(
                "usable_frames"
            ),
            "/",
            result.get(
                "required_frames"
            ),
        )

        if not result["valid"]:

            failures.append(
                (
                    item.beat_id,
                    result,
                )
            )

    print()
    print(
        "========== QUALITY FAILURES =========="
    )

    if not failures:
        print("NONE")

    for beat_id, result in failures:

        print()
        print(
            beat_id,
            result,
        )


asyncio.run(main())
