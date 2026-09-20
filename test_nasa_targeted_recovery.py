import asyncio

from backend.services.video.visual_beat_source_planner import (
    VisualBeatSourcePlanner,
)
from backend.services.video.targeted_beat_resolver import (
    TargetedBeatResolver,
)
from backend.services.video.media_sources.nasa import (
    NasaVideoProvider,
)
from backend.services.video.media_sources.wikimedia import (
    WikimediaCommonsProvider,
)
from backend.services.video.media_sources.internet_archive import (
    InternetArchiveProvider,
)


async def main():

    planner = VisualBeatSourcePlanner()

    beats = await planner.plan(
        topic="how jet engines work",
        format_name="science_explainer",
        beat_count=8,
    )

    resolver = TargetedBeatResolver(
        providers=[
            NasaVideoProvider(),
            WikimediaCommonsProvider(),
            InternetArchiveProvider(),
        ]
    )

    targets = [
        beat
        for beat in beats
        if beat.beat_id in {
            "b1",
            "b5",
        }
    ]

    for beat in targets:

        print()
        print(
            "========================================"
        )

        print(
            "NASA-FIRST RESOLVING:",
            beat.beat_id,
        )

        print(
            "GOAL:",
            beat.visual_goal,
        )

        result = await resolver.resolve(
            beat=beat,
            content_id=(
                "jet-nasa-recovery-001"
            ),
        )

        print(
            "STATUS:",
            result.status,
        )

        print(
            "QUERIES:",
            result.attempted_queries,
        )

        if result.match is not None:

            print(
                "MATCH:",
                result.match.clip_id,
            )

            print(
                "SOURCE:",
                result.match.source_name,
            )

            print(
                "TIME:",
                result.match.start_time,
                "->",
                result.match.end_time,
            )

            print(
                "PREVIEW:",
                result.match.preview_path,
            )

            print(
                "SEMANTIC SCORE:",
                result.match.final_score,
            )

        else:

            print(
                "NO VERIFIED VISUAL"
            )

        print()
        print(
            "LAST REJECTIONS:"
        )

        for reason in (
            result.rejection_reasons
        )[-12:]:

            print(
                "-",
                reason,
            )


asyncio.run(main())
