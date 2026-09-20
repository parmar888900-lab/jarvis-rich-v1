import asyncio

from backend.services.content_generator import ContentGenerator


async def main():

    generator = ContentGenerator()

    trend = {
        "title": "Why AI-generated videos are becoming more realistic",
        "research": (
            "AI video systems are improving rapidly in image quality, "
            "motion consistency, voice generation, and automated editing. "
            "Creators increasingly use AI tools to generate scripts, "
            "visuals, narration, captions, and final videos."
        ),
    }

    print("QWEN CONTENT TEST START")
    print()

    content = await generator.generate(
        trend
    )

    print()
    print("RESULT")
    print("TITLE:", content.title)
    print("HASHTAGS:", content.hashtags)

    print()
    print("SCRIPT:")

    for index, line in enumerate(
        content.script_lines,
        start=1,
    ):
        print(
            f"{index}. {line}"
        )

    word_count = sum(
        len(line.split())
        for line in content.script_lines
    )

    print()
    print("WORD COUNT:", word_count)

    estimated_seconds = (
        word_count / 2.5
    )

    print(
        "ESTIMATED NARRATION:",
        round(
            estimated_seconds,
            1,
        ),
        "seconds",
    )


asyncio.run(main())
