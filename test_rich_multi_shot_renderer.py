import asyncio

from backend.models.generated_content import GeneratedContent
from backend.services.storyboard.movie_visual_beat_planner import (
    MovieVisualBeatPlanner,
)
from backend.services.video.movie_media_resolver import (
    MovieMediaResolver,
)
from backend.services.video.reference_profiles import (
    get_profile,
)
from backend.services.video_renderer.rich_multi_shot_renderer import (
    RichMultiShotRenderer,
)


async def main():

    content = GeneratedContent(
        title="Doctor Strange Rich Renderer Test",
        script_lines=[
            (
                "Doctor Strange's mirror dimension "
                "creates surreal visual effects."
            ),
            (
                "The film uses dimensional action "
                "and unusual geometry."
            ),
            (
                "Its visual effects give the scenes "
                "a distinctive cinematic look."
            ),
            (
                "That makes the sequence visually "
                "memorable."
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
            "dimension works"
        ),
    )

    resolver = MovieMediaResolver()

    resolved = await resolver.resolve(
        beats=beats,
        content_id=(
            "rich-render-test-001"
        ),
        movie_title="Doctor Strange",
    )

    assets = [
        item.asset
        for item in resolved
        if item.asset is not None
    ]

    if not assets:
        raise RuntimeError(
            "Renderer test produced no assets."
        )

    profile = get_profile(
        "movie_facts"
    )

    renderer = RichMultiShotRenderer()

    result = await renderer.render(
        title=content.title,
        assets=assets,
        profile=profile,
    )

    print()
    print(
        "========== RICH RENDER TEST =========="
    )

    for key, value in result.items():
        print(
            key,
            ":",
            value,
        )


asyncio.run(main())
