import asyncio

from backend.services.video.visual_beat_source_planner import (
    VisualBeatSourcePlanner,
)
from backend.services.video.targeted_beat_resolver import (
    TargetedBeatResolver,
)


async def main():

    planner = VisualBeatSourcePlanner()

    beats = await planner.plan(
        topic="how jet engines work",
        format_name="science_explainer",
        beat_count=8,
    )

    resolver = TargetedBeatResolver()

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
            "RESOLVING:",
            beat.beat_id,
            beat.visual_goal,
        )

        result = await resolver.resolve(
            beat=beat,
            content_id=(
                "jet-targeted-research-001"
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
                "SCORE:",
                result.match.final_score,
            )

        else:

            print(
                "NO ACCEPTABLE VISUAL FOUND"
            )

        print()
        print(
            "REJECTIONS:"
        )

        for reason in (
            result.rejection_reasons
        )[-10:]:

            print(
                "-",
                reason,
            )


asyncio.run(main())
