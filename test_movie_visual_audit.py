import asyncio
import shutil
import webbrowser
from pathlib import Path

from backend.models.generated_content import GeneratedContent
from backend.services.storyboard.movie_visual_beat_planner import (
    MovieVisualBeatPlanner,
)
from backend.services.video.movie_media_resolver import (
    MovieMediaResolver,
)
from backend.services.video.visual_audit import (
    VisualAuditGenerator,
)


CONTENT_ID = "doctor-strange-visual-audit-001"


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

    resolver = MovieMediaResolver()

    result = await resolver.resolve(
        beats=beats,
        content_id=CONTENT_ID,
        movie_title="Doctor Strange",
    )

    audit = VisualAuditGenerator(
        ffmpeg_binary=(
            shutil.which("ffmpeg")
            or "ffmpeg"
        )
    )

    html_path = audit.generate(
        resolved_beats=result,
        content_id=CONTENT_ID,
    )

    resolved = [
        item
        for item in result
        if item.status == "resolved"
    ]

    thumbnails = list(
        (
            html_path.parent
            / "thumbnails"
        ).glob("*.jpg")
    )

    print()
    print(
        "========== VISUAL AUDIT =========="
    )
    print(
        "BEATS:",
        len(result),
    )
    print(
        "RESOLVED:",
        len(resolved),
    )
    print(
        "THUMBNAILS:",
        len(thumbnails),
    )
    print(
        "HTML:",
        html_path.resolve(),
    )
    print(
        "JSON:",
        (
            html_path.parent
            / "audit.json"
        ).resolve(),
    )

    print()
    print(
        "========== SELECTED ASSETS =========="
    )

    for item in result:

        if item.asset is None:
            print(
                item.beat_id,
                "| UNRESOLVED",
            )
            continue

        print(
            item.beat_id,
            "|",
            item.asset.asset_type,
            "|",
            item.asset.source_name,
            "|",
            item.asset.relevance_score,
            "|",
            item.asset.file_path,
        )

    webbrowser.open(
        html_path.resolve().as_uri()
    )


asyncio.run(main())
