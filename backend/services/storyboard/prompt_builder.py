"""
Builds cinematic image prompts for AI image generation.
"""

from backend.models.generated_content import GeneratedContent
from backend.services.storyboard.scene import Scene


class PromptBuilder:
    """
    Converts narration into detailed cinematic image prompts.

    This is intentionally model-agnostic so it can be used with:
        - Flux
        - SDXL
        - Ideogram
        - Midjourney
        - DALL·E
    """

    BASE_STYLE = (
        "ultra realistic, cinematic lighting, 8k, highly detailed, "
        "professional composition, dramatic atmosphere, volumetric lighting, "
        "sharp focus, masterpiece"
    )

    def build(
        self,
        content: GeneratedContent,
        scene: Scene,
    ) -> str:
        """
        Generate a cinematic prompt for one scene.
        """

        prompt = (
            f"{scene.narration}. "
            f"Topic: {content.title}. "
            f"{self.BASE_STYLE}."
        )

        return prompt