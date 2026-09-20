from backend.services.image_generation.base_provider import (
    BaseImageProvider,
)
from backend.services.image_generation.cloudflare_flux_provider import (
    CloudflareFluxProvider,
)
from backend.services.image_generation.flux_provider import FluxProvider
from backend.services.image_generation.prompt_enhancer import PromptEnhancer
from backend.services.runtime.runtime_config import RuntimeConfig


class ImageGenerator:

    def __init__(
        self,
        runtime_config: RuntimeConfig | None = None,
        provider: BaseImageProvider | None = None,
    ):
        config = (
            runtime_config
            if runtime_config is not None
            else RuntimeConfig.from_environment()
        )

        self.provider = (
            provider
            if provider is not None
            else self._build_provider(
                config
            )
        )

        self.enhancer = PromptEnhancer()

    @staticmethod
    def _build_provider(
        config: RuntimeConfig,
    ) -> BaseImageProvider:

        provider_name = (
            config.image_provider
            .strip()
            .lower()
        )

        if provider_name in {
            "comfyui",
            "flux",
            "flux-comfyui",
        }:
            return FluxProvider(
                runtime_config=config
            )

        if provider_name in {
            "cloudflare",
            "flux-cloudflare",
        }:
            return CloudflareFluxProvider(
                runtime_config=config
            )

        raise ValueError(
            "Unsupported image provider: "
            f"{config.image_provider}"
        )

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
