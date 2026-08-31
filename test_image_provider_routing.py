import asyncio
import tempfile
from dataclasses import replace
from pathlib import Path

from backend.services.image_generation.base_provider import (
    BaseImageProvider,
)
from backend.services.image_generation.cloudflare_flux_provider import (
    CloudflareFluxProvider,
)
from backend.services.image_generation.flux_provider import FluxProvider
from backend.services.image_generation.generator import ImageGenerator
from backend.services.image_generation.models import GeneratedImage
from backend.services.runtime.runtime_config import RuntimeConfig


def make_config(
    root: Path,
    provider: str = "comfyui",
) -> RuntimeConfig:

    return RuntimeConfig(
        ollama_base_url="http://localhost:11434",
        ollama_model="qwen2.5:7b",
        comfyui_url="http://127.0.0.1:8188",
        comfyui_output_dir=root / "comfy",
        flux_workflow_path=Path(
            "configs/workflows/flux_api.json"
        ),
        piper_executable=Path("piper"),
        piper_model_path=Path("voice.onnx"),
        ffmpeg_executable="ffmpeg",
        generated_dir=root,
        database_url="",
        youtube_token_path=Path("token.json"),
        youtube_client_secret_path=Path(
            "secret.json"
        ),
        image_provider=provider,
        cloudflare_account_id="fake-account",
        cloudflare_api_token="fake-token",
        cloudflare_flux_model=(
            "@cf/black-forest-labs/"
            "flux-1-schnell"
        ),
    )


def test_comfyui_selection():

    with tempfile.TemporaryDirectory() as temp:

        config = make_config(
            Path(temp),
            "comfyui",
        )

        generator = ImageGenerator(
            runtime_config=config
        )

        assert isinstance(
            generator.provider,
            FluxProvider,
        )

        print(
            "PASS: comfyui selects FluxProvider."
        )


def test_cloudflare_selection():

    with tempfile.TemporaryDirectory() as temp:

        config = make_config(
            Path(temp),
            "cloudflare",
        )

        generator = ImageGenerator(
            runtime_config=config
        )

        assert isinstance(
            generator.provider,
            CloudflareFluxProvider,
        )

        print(
            "PASS: cloudflare selects "
            "CloudflareFluxProvider."
        )


def test_aliases():

    with tempfile.TemporaryDirectory() as temp:

        root = Path(temp)

        base = make_config(
            root
        )

        for name in (
            "flux",
            "flux-comfyui",
        ):
            config = replace(
                base,
                image_provider=name,
            )

            generator = ImageGenerator(
                runtime_config=config
            )

            assert isinstance(
                generator.provider,
                FluxProvider,
            )

        for name in (
            "cloudflare",
            "flux-cloudflare",
        ):
            config = replace(
                base,
                image_provider=name,
            )

            generator = ImageGenerator(
                runtime_config=config
            )

            assert isinstance(
                generator.provider,
                CloudflareFluxProvider,
            )

        print(
            "PASS: provider aliases route correctly."
        )


def test_invalid_provider():

    with tempfile.TemporaryDirectory() as temp:

        config = make_config(
            Path(temp),
            "not-a-provider",
        )

        try:
            ImageGenerator(
                runtime_config=config
            )
        except ValueError as exc:
            assert (
                "unsupported image provider"
                in str(exc).lower()
            )
        else:
            raise AssertionError(
                "Unknown image provider "
                "did not fail closed."
            )

        print(
            "PASS: unknown provider fails closed."
        )


class FakeProvider(BaseImageProvider):

    def __init__(self):
        self.prompt = None

    async def generate(
        self,
        prompt: str,
    ) -> GeneratedImage:

        self.prompt = prompt

        return GeneratedImage(
            prompt=prompt,
            image_path="fake.png",
            provider="fake",
            width=720,
            height=1280,
        )


class FakeScene:

    image_prompt = "a futuristic city"


async def test_provider_injection():

    with tempfile.TemporaryDirectory() as temp:

        config = make_config(
            Path(temp)
        )

        provider = FakeProvider()

        generator = ImageGenerator(
            runtime_config=config,
            provider=provider,
        )

        result = await generator.generate(
            FakeScene()
        )

        assert result.provider == "fake"

        assert provider.prompt is not None

        assert (
            "a futuristic city"
            in provider.prompt
        )

        assert (
            "cinematic"
            in provider.prompt
        )

        print(
            "PASS: injected provider receives "
            "enhanced prompt."
        )


async def main():

    test_comfyui_selection()
    test_cloudflare_selection()
    test_aliases()
    test_invalid_provider()

    await test_provider_injection()

    print(
        "\nPASS: ImageGenerator provider "
        "routing regression suite complete."
    )


if __name__ == "__main__":
    asyncio.run(main())
