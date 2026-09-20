import asyncio
import json

from backend.models.generated_content import GeneratedContent
from backend.services.content_generator import ContentGenerator
from backend.services.content_validator import ContentValidator


class FakeLLM:

    async def chat(
        self,
        messages,
        model=None,
        json_mode=False,
    ):

        return json.dumps(
            {
                "title": "AI Video Is Improving",
                "hashtags": [
                    "#ai",
                    "#video",
                    "#technology",
                ],
                "script_lines": [
                    (
                        "AI-generated video is becoming "
                        "more realistic as image quality "
                        "and motion consistency continue "
                        "to improve across newer tools."
                    ),
                    (
                        "Creators are also using AI "
                        "systems for scripts, narration, "
                        "captions, visuals, and other "
                        "parts of the production process."
                    ),
                    (
                        "These tools can make some video "
                        "workflows faster, although the "
                        "quality still depends heavily "
                        "on the model and source material."
                    ),
                    (
                        "The technology is developing "
                        "quickly, but results still vary "
                        "between systems and use cases. "
                        "What changes do you expect next?"
                    ),
                ],
            }
        )


async def main():

    generator = ContentGenerator()
    generator.llm = FakeLLM()

    validator = ContentValidator()

    unsafe = GeneratedContent(
        title="Unsafe AI Video",
        hashtags=[
            "#ai",
            "#video",
            "#technology",
        ],
        script_lines=[
            (
                "AI-generated videos are "
                "indistinguishable from "
                "human-made videos."
            ),
            (
                "The technology is guaranteed "
                "to replace traditional tools."
            ),
            (
                "Creators are testing "
                "new production systems."
            ),
            (
                "AI video will always "
                "change everything."
            ),
        ],
        metadata={},
    )

    initial_validation = validator.validate(
        unsafe
    )

    print(
        "INITIAL VALID:",
        initial_validation["valid"],
    )

    repaired = await generator.repair(
        content=unsafe,
        trend={
            "title": (
                "Why AI-generated videos "
                "are becoming more realistic"
            ),
            "research": (
                "AI video systems are improving "
                "in image quality and motion "
                "consistency. Creators also use "
                "AI tools for scripts, narration, "
                "captions, visuals, and editing."
            ),
        },
        issues=initial_validation["issues"],
    )

    print(
        "REPAIR RETURNED:",
        repaired is not None,
    )

    if repaired is None:
        print(
            "FAIL: repair returned None."
        )
        return

    final_validation = validator.validate(
        repaired
    )

    print(
        "FINAL VALID:",
        final_validation["valid"],
    )

    print(
        "REPAIRED FLAG:",
        repaired.metadata.get(
            "repaired"
        ),
    )

    print(
        "WORD COUNT:",
        repaired.metadata.get(
            "word_count"
        ),
    )

    print(
        "SCRIPT:"
    )

    for index, line in enumerate(
        repaired.script_lines,
        start=1,
    ):
        print(
            f"{index}. {line}"
        )

    if (
        not initial_validation["valid"]
        and repaired is not None
        and final_validation["valid"]
        and repaired.metadata.get(
            "repaired"
        ) is True
    ):
        print()
        print(
            "PASS: unsafe content was "
            "successfully repaired."
        )

    else:
        print()
        print(
            "FAIL: repair test did "
            "not meet expectations."
        )


asyncio.run(
    main()
)
