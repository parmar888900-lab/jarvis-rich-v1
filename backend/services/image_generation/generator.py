from backend.services.image_generation.flux_provider import FluxProvider
from backend.services.image_generation.prompt_enhancer import PromptEnhancer


class ImageGenerator:

    def __init__(self):

        self.provider = FluxProvider()

        self.enhancer = PromptEnhancer()

    async def generate(
        self,
        scene,
    ):

        prompt = self.enhancer.enhance(
            scene.image_prompt
        )

        return await self.provider.generate(
            prompt
        )