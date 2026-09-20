import asyncio
import json

from backend.services.agent_handlers.youtube import (
    YoutubeAgentHandler,
)


async def main():
    handler = YoutubeAgentHandler()

    print("\n========== SELECTING TOPIC ==========\n")

    analysis = await handler.execute(
        task="analyze_trends",
        command_id="reference-style-test-001:analyze",
    )

    if analysis.get("status") != "success":
        print(json.dumps(analysis, indent=2))
        raise RuntimeError(
            "Evergreen topic selection failed."
        )

    topic = analysis["best_trend"]

    print("TITLE:", topic.get("title"))
    print("GENRE:", topic.get("genre"))
    print("CONTENT ID:", topic.get("content_id"))

    print("\n========== PRODUCING VIDEO ==========\n")

    result = await handler.execute(
        task="create_video",
        command_id="reference-style-test-001:produce",
        trend=topic,
    )

    print("\n========== RESULT ==========\n")

    print("STATUS:", result.get("status"))

    generated = result.get(
        "generated_content",
        {},
    )

    print("\nTITLE:")
    print(generated.get("title"))

    print("\nSCRIPT:")
    for line in generated.get(
        "script_lines",
        [],
    ):
        print("-", line)

    package = result.get(
        "production_package",
        {},
    )

    print("\nPACKAGE:")
    print(package.get("package_dir"))

    video = result.get(
        "video",
        {},
    )

    print("\nVIDEO:")
    print(video.get("video_path"))

    print("\nDURATION:")
    print(video.get("duration"))

    print("\nCAPTION MODE:")
    print(video.get("caption_mode"))


asyncio.run(main())
