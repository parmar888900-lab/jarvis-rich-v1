import asyncio

from backend.models.generated_content import GeneratedContent
from backend.services.storyboard.movie_visual_beat_planner import (
    MovieVisualBeatPlanner,
)
from backend.services.video.movie_media_resolver import (
    MovieMediaResolver,
)
from backend.services.video.visual_semantic_validator import (
    VisualSemanticValidator,
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
        content_id="visual-semantic-calibration-001",
        movie_title="Doctor Strange",
    )

    validator = VisualSemanticValidator()

    print()
    print("========== VISUAL SEMANTIC CALIBRATION ==========")

    scores = []

    for beat, item in zip(beats, resolved):

        if item.asset is None:
            print(
                beat.beat_id,
                "| UNRESOLVED"
            )
            continue

        result = validator.validate(
            asset=item.asset,
            beat=beat,
            movie_title="Doctor Strange",
        )

        scores.append(
            (
                beat.beat_id,
                result["score"],
                result["valid"],
                item.asset.source_name,
                item.asset.asset_type,
                beat.visual_query,
            )
        )

        print(
            beat.beat_id,
            "|",
            result["score"],
            "|",
            result["valid"],
            "|",
            item.asset.source_name,
            "|",
            item.asset.asset_type,
            "|",
            beat.visual_query,
        )

    print()
    print("========== SORTED LOWEST TO HIGHEST ==========")

    for row in sorted(
        scores,
        key=lambda item: item[1],
    ):
        print(
            row[0],
            "|",
            row[1],
            "|",
            row[2],
            "|",
            row[3],
            "|",
            row[4],
            "|",
            row[5],
        )


asyncio.run(main())
