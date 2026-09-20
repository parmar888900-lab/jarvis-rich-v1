import asyncio

from backend.models.generated_content import GeneratedContent
from backend.services.content_generator import ContentGenerator
from backend.services.content_validator import ContentValidator


async def main():

    generator = ContentGenerator()
    validator = ContentValidator()

    trend = {
        "title": (
            "Why AI-generated videos "
            "are becoming more realistic"
        ),
        "research": (
            "AI video systems are improving rapidly "
            "in image quality, motion consistency, "
            "voice generation, and automated editing. "
            "Creators increasingly use AI tools to "
            "generate scripts, visuals, narration, "
            "captions, and final videos."
        ),
    }

    unsafe = GeneratedContent(
        title=trend["title"],
        hashtags=[
            "#ai",
            "#video",
            "#technology",
        ],
        script_lines=[
            (
                "AI-generated videos are now "
                "indistinguishable from videos "
                "created entirely by humans."
            ),
            (
                "These systems are guaranteed "
                "to replace traditional video "
                "production tools."
            ),
            (
                "Creators are increasingly using "
                "AI for scripts, visuals, "
                "narration, captions, and editing."
            ),
            (
                "AI will always produce better "
                "video as the technology "
                "continues improving."
            ),
        ],
        metadata={},
    )

    before = validator.validate(
        unsafe
    )

    print("BEFORE VALID:", before["valid"])
    print("ISSUES:", before["issues"])
    print()

    repaired = await generator.repair(
        content=unsafe,
        trend=trend,
        issues=before["issues"],
    )

    if repaired is None:
        print("REPAIR RETURNED: None")
        print("FAIL: Qwen repair failed structural/length validation.")
        return

    after = validator.validate(
        repaired
    )

    print("REPAIR RETURNED: True")
    print("AFTER VALID:", after["valid"])
    print(
        "WORD COUNT:",
        repaired.metadata.get("word_count"),
    )
    print(
        "REPAIRED FLAG:",
        repaired.metadata.get("repaired"),
    )

    print()
    print("REPAIRED SCRIPT:")

    for index, line in enumerate(
        repaired.script_lines,
        start=1,
    ):
        print(f"{index}. {line}")

    print()
    print("REMAINING ISSUES:", after["issues"])

    if (
        after["valid"]
        and repaired.metadata.get("repaired") is True
        and 75 <= repaired.metadata.get(
            "word_count",
            0,
        ) <= 105
    ):
        print()
        print(
            "PASS: real Qwen repair produced "
            "structurally valid content that "
            "passed the deterministic validator."
        )
    else:
        print()
        print(
            "FAIL: real Qwen output did not "
            "meet repair requirements."
        )


asyncio.run(main())
