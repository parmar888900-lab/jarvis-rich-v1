import asyncio

from backend.models.generated_content import GeneratedContent
from backend.services.pipelines.video_pipeline import VideoPipeline


class FakeGenerator:

    async def generate(
        self,
        trend,
    ):

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
                    "The technology is guaranteed "
                    "to replace existing tools."
                ),
                (
                    "Creators are experimenting "
                    "with AI production systems."
                ),
                (
                    "AI will always change "
                    "video production."
                ),
            ],
            metadata={},
        )

    async def repair(
        self,
        content,
        trend,
        issues,
    ):

        print(
            "REPAIR CALLED:",
            True,
        )

        print(
            "ISSUES RECEIVED:",
            len(issues),
        )

        return GeneratedContent(
            title="Repaired Test",
            hashtags=[
                "#ai",
                "#video",
                "#test",
            ],
            script_lines=[
                (
                    "AI video systems are improving "
                    "in image quality and motion "
                    "consistency as developers "
                    "continue refining newer tools."
                ),
                (
                    "Creators can use these systems "
                    "for scripts, visuals, narration, "
                    "captions, and several other "
                    "parts of video production."
                ),
                (
                    "The tools may make some "
                    "production workflows faster, "
                    "although results still depend "
                    "on the models and source material."
                ),
                (
                    "AI-assisted video continues "
                    "to develop across different "
                    "systems and use cases, with "
                    "quality varying between tools."
                ),
            ],
            metadata={
                "repaired": True,
            },
        )


class FakeStoryboard:

    def generate(
        self,
        content,
    ):

        print(
            "STORYBOARD REACHED:",
            True,
        )

        print(
            "CONTENT REPAIRED:",
            content.metadata.get(
                "repaired"
            ),
        )

        return [
            "scene-1",
            "scene-2",
            "scene-3",
            "scene-4",
        ]


class FakeImageGenerator:

    async def generate(
        self,
        scene,
    ):

        return f"image-for-{scene}"


class FakePackageBuilder:

    async def build(
        self,
        content,
        scenes,
        images,
        trend,
    ):

        return {
            "status": "fake-package",
        }


class FakeRenderer:

    async def render(
        self,
        content,
        scenes,
        images,
        production_package,
    ):

        return {
            "status": "fake-video",
        }


async def main():

    pipeline = VideoPipeline()

    pipeline.generator = (
        FakeGenerator()
    )

    pipeline.storyboard = (
        FakeStoryboard()
    )

    pipeline.image_generator = (
        FakeImageGenerator()
    )

    pipeline.package_builder = (
        FakePackageBuilder()
    )

    pipeline.renderer = (
        FakeRenderer()
    )

    result = await pipeline.run(
        {
            "title": "Test",
            "research": (
                "AI video systems are improving "
                "in image quality and motion "
                "consistency. Creators use AI "
                "for several production tasks."
            ),
        }
    )

    print()
    print(
        "PIPELINE STATUS:",
        result["status"],
    )

    print(
        "FINAL VALID:",
        result[
            "content_validation"
        ]["valid"],
    )

    print(
        "FINAL REPAIRED:",
        result[
            "generated"
        ].metadata.get(
            "repaired"
        ),
    )

    print(
        "IMAGE COUNT:",
        len(
            result["images"]
        ),
    )

    if (
        result["status"] == "success"
        and result[
            "content_validation"
        ]["valid"]
        and result[
            "generated"
        ].metadata.get(
            "repaired"
        ) is True
        and len(
            result["images"]
        ) == 4
    ):
        print()
        print(
            "PASS: reject -> repair -> "
            "validate -> production flow works."
        )

    else:
        print()
        print(
            "FAIL: integration test "
            "did not meet expectations."
        )


asyncio.run(
    main()
)
