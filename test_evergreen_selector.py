import asyncio

from backend.services.agent_handlers.youtube import (
    YoutubeAgentHandler,
)


async def main():
    handler = YoutubeAgentHandler()

    result = await handler.execute(
        task="analyze_trends",
        command_id="evergreen-test-001:analyze",
    )

    print("\nSTATUS:", result.get("status"))
    print(
        "STRATEGY:",
        result.get("content_strategy"),
    )
    print(
        "TREND SYSTEM ACTIVE:",
        result.get("trend_system_active"),
    )

    topic = result.get(
        "best_trend",
        {},
    )

    print("\nTITLE:", topic.get("title"))
    print("GENRE:", topic.get("genre"))
    print(
        "CONTENT ID:",
        topic.get("content_id"),
    )
    print(
        "REQUIRES TREND:",
        topic.get("requires_trend"),
    )

    selection = topic.get(
        "production_selection",
        {},
    )

    print(
        "ELIGIBLE:",
        selection.get("eligible"),
    )
    print(
        "SELECTED:",
        selection.get("selected"),
    )
    print(
        "SCORE:",
        selection.get("production_score"),
    )


asyncio.run(main())
