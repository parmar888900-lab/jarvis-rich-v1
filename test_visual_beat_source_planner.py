import asyncio

from backend.services.video.visual_beat_source_planner import (
    VisualBeatSourcePlanner,
)


async def main():

    planner = VisualBeatSourcePlanner()

    beats = await planner.plan(
        topic="how jet engines work",
        format_name="science_explainer",
        beat_count=8,
    )

    print()
    print("========== SOURCE VISUAL PLAN ==========")

    for beat in beats:

        print()
        print(
            beat.beat_id,
            "|",
            beat.purpose,
            "|",
            beat.visual_goal,
        )

        print(
            "SEARCH:",
            beat.search_queries,
        )

        print(
            "REJECT:",
            beat.negative_visuals,
        )


asyncio.run(main())
