"""
Central video production pipeline.

Responsibilities:
    - Generate content
    - Build storyboard
    - Generate images
    - Build production package
    - Render final video

This class ONLY orchestrates the workflow.
"""


from backend.services.content_generator import ContentGenerator
from backend.services.storyboard.generator import StoryboardGenerator
from backend.services.image_generation.generator import ImageGenerator
from backend.services.video.production_package import ProductionPackageBuilder
from backend.services.video_renderer.renderer import VideoRenderer


class VideoPipeline:

    def __init__(self):

        self.generator = ContentGenerator()

        self.storyboard = StoryboardGenerator()

        self.image_generator = ImageGenerator()

        self.package_builder = ProductionPackageBuilder()

        self.renderer = VideoRenderer()

    async def run(
        self,
        trend: dict,
    ) -> dict:

        ####################################################
        # 1. Generate content
        ####################################################

        generated = await self.generator.generate(
            trend
        )

        if generated is None:
            raise RuntimeError(
                "ContentGenerator returned None."
            )

        ####################################################
        # 2. Build storyboard
        ####################################################

        storyboard = self.storyboard.generate(
            generated
        )

        if not storyboard:
            raise RuntimeError(
                "StoryboardGenerator produced no scenes."
            )

        ####################################################
        # 3. Generate images
        ####################################################

        images = []

        for scene in storyboard:

            image = await self.image_generator.generate(
                scene
            )

            images.append(image)

        if len(images) != len(storyboard):
            raise RuntimeError(
                "Storyboard/image count mismatch."
            )

        ####################################################
        # 4. Build production package
        ####################################################

        package = await self.package_builder.build(

            content=generated,

            scenes=storyboard,

            images=images,

            trend=trend,

        )

        ####################################################
        # 5. Render final video
        ####################################################

        video = await self.renderer.render(

            content=generated,

            scenes=storyboard,

            images=images,

            production_package=package,

        )

        ####################################################
        # 6. Return everything
        ####################################################

        return {

            "generated": generated,

            "storyboard": storyboard,

            "images": images,

            "production_package": package,

            "video": video,

            "status": "success",

        }

