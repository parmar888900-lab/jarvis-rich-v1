"""
Central video production pipeline.

Responsibilities:
    - Generate content
    - Validate content
    - Repair rejected content
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

        ####################################################
        # 3. Repair rejected content
        ####################################################

        if not validation["valid"]:

            repaired = await self.generator.repair(
                content=generated,
                trend=trend,
                issues=validation["issues"],
            )

            if repaired is None:
                raise RuntimeError(
                    "Generated content failed validation "
                    "and automatic repair failed."
                )

            repaired_validation = (
                self.content_validator.validate(
                    repaired
                )
            )

            if not repaired_validation["valid"]:
                raise RuntimeError(
                    "Repaired content still failed "
                    "factual grounding validation: "
                    f"{repaired_validation['issues']}"
                )

            generated = repaired
            validation = repaired_validation

        ####################################################
        # 4. Build storyboard
        ####################################################

        storyboard = self.storyboard.generate(
            generated
        )

        if not storyboard:
            raise RuntimeError(
                "StoryboardGenerator produced no scenes."
            )

        ####################################################
        # 5. Generate images
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
        # 6. Build production package
        ####################################################

        package = await self.package_builder.build(

            content=generated,

            scenes=storyboard,

            images=images,

            trend=trend,

        )

        ####################################################
        # 7. Render final video
        ####################################################

        video = await self.renderer.render(

            content=generated,

            scenes=storyboard,

            images=images,

            production_package=package,

        )

        ####################################################
        # 8. Return everything
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
