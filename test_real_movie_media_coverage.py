import asyncio

from backend.models.generated_content import GeneratedContent
from backend.services.storyboard.movie_visual_beat_planner import (
    MovieVisualBeatPlanner,
)
from backend.services.video.movie_media_resolver import (
    MovieMediaResolver,
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

    result = await resolver.resolve(
        beats=beats,
        content_id="doctor-strange-coverage-test-001",
        movie_title="Doctor Strange",
    )

    resolved = [
        item
        for item in result
        if item.status == "resolved"
    ]

    unresolved = [
        item
        for item in result
        if item.status != "resolved"
    ]

    print()
    print("========== REAL MOVIE MEDIA COVERAGE ==========")
    print("TOTAL:", len(result))
    print("RESOLVED:", len(resolved))
    print("UNRESOLVED:", len(unresolved))
    print(
        "COVERAGE:",
        round(
            len(resolved)
            / len(result)
            * 100,
            1,
        ),
        "%",
    )

    print()
    print("========== RESOLVED ==========")

    for item in resolved:

        print(
            item.beat_id,
            "|",
            item.asset.asset_type,
            "|",
            item.asset.license_name,
            "|",
            item.asset.relevance_score,
            "|",
            item.visual_query,
        )

    print()
    print("========== UNRESOLVED ==========")

    for item in unresolved:

        print(
            item.beat_id,
            "|",
            item.visual_query,
            "|",
            item.attempted_queries,
        )


asyncio.run(main())
