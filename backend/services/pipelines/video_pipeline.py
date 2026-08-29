"""
Central video production pipeline.

Responsibilities:
    - Generate content
    - Validate content
    - Build storyboard
    - Generate images
    - Build production package
    - Render final video

This class ONLY orchestrates the workflow.
"""


from backend.services.content_generator import ContentGenerator
from backend.services.content_validator import ContentValidator
from backend.services.storyboard.generator import StoryboardGenerator
from backend.services.image_generation.generator import ImageGenerator
from backend.services.video.production_package import ProductionPackageBuilder
from backend.services.video_renderer.renderer import VideoRenderer


class VideoPipeline:

    def __init__(self):

        self.generator = ContentGenerator()

        self.content_validator = ContentValidator()

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
        # 2. Validate generated content
        ####################################################

        validation = self.content_validator.validate(
            generated
        )

        if not validation["valid"]:

            raise RuntimeError(
                "Generated content failed factual "
                "grounding validation: "
                f"{validation['issues']}"
            )

        ####################################################
        # 3. Build storyboard
        ####################################################

        storyboard = self.storyboard.generate(
            generated
        )

        if not storyboard:
            raise RuntimeError(
                "StoryboardGenerator produced no scenes."
            )

        ####################################################
        # 4. Generate images
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
        # 5. Build production package
        ####################################################

        package = await self.package_builder.build(

            content=generated,

            scenes=storyboard,

            images=images,

            trend=trend,

        )

        ####################################################
        # 6. Render final video
        ####################################################

        video = await self.renderer.render(

            content=generated,

            scenes=storyboard,

            images=images,

            production_package=package,

        )

        ####################################################
        # 7. Return everything
        ####################################################

        return {

            "generated": generated,

            "content_validation": validation,

            "storyboard": storyboard,

            "images": images,

            "production_package": package,

            "video": video,

            "status": "success",

        }
