import asyncio

from backend.models.generated_content import GeneratedContent
from backend.services.pipelines.video_pipeline import VideoPipeline


class UnsafeGenerator:

    async def generate(self, trend):

        return GeneratedContent(
            title="Unsafe Test",
            hashtags=[
                "#ai",
                "#video",
                "#test",
            ],
            script_lines=[
                (
                    "AI-generated videos are "
                    "indistinguishable from "
                    "human-made videos."
                ),
                (
                    "The technology is "
                    "improving rapidly."
                ),
                (
                    "Creators are testing "
                    "new production tools."
                ),
                (
                    "The future is guaranteed "
                    "to change everything."
                ),
            ],
            metadata={},
        )


class TrapStoryboard:

    def generate(self, content):

        raise RuntimeError(
            "ERROR: storyboard should "
            "never have been reached."
        )


async def main():

    pipeline = VideoPipeline()

    pipeline.generator = (
        UnsafeGenerator()
    )

    pipeline.storyboard = (
        TrapStoryboard()
    )

    print(
        "PIPELINE CONTENT GATE TEST"
    )

    try:

        await pipeline.run(
            {
                "title": "Test"
            }
        )

    except RuntimeError as exc:

        print()
        print(
            "BLOCKED:",
            exc,
        )

        if (
            "failed factual grounding"
            in str(exc)
        ):

            print()
            print(
                "PASS: unsafe content "
                "was blocked before "
                "storyboard/FLUX."
            )

        else:

            print()
            print(
                "FAIL: unexpected "
                "pipeline error."
            )


asyncio.run(
    main()
)
