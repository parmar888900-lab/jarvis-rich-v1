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
        title="Doctor Strange visual test",
        script_lines=[
            (
                "Doctor Strange's mirror dimension "
                "uses surreal visual effects."
            ),
            (
                "The director wanted different "
                "dimensions in the action."
            ),
            (
                "The production relied heavily "
                "on visual effects."
            ),
            (
                "The result was visually distinct."
            ),
        ],
        metadata={
            "content_format": (
                "famous_movie_commentary"
            ),
            "movie_title": "Doctor Strange",
            "evidence_ids": [
                ["E3"],
                ["E3"],
                ["E4"],
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
        beats=beats[:1],
        content_id="visual-semantic-smoke-001",
        movie_title="Doctor Strange",
    )

    item = resolved[0]

    if item.asset is None:
        raise RuntimeError(
            "Smoke test beat unresolved."
        )

    validator = VisualSemanticValidator()

    result = validator.validate(
        asset=item.asset,
        beat=beats[0],
        movie_title="Doctor Strange",
    )

    print()
    print(
        "========== VISUAL SEMANTIC SMOKE =========="
    )

    print(
        "BEAT:",
        beats[0].beat_id,
    )

    print(
        "QUERY:",
        beats[0].visual_query,
    )

    print(
        "ASSET:",
        item.asset.file_path,
    )

    print(
        "RESULT:",
        result,
    )


asyncio.run(main())
