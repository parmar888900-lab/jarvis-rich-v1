import tempfile
from pathlib import Path

from backend.services.image_generation.image_cache import (
    ImageCache,
)
from backend.services.runtime.runtime_config import (
    RuntimeConfig,
)
from backend.services.video.production_package import (
    ProductionPackageBuilder,
)


def build_config(
    root: Path,
) -> RuntimeConfig:
    return RuntimeConfig(
        ollama_base_url="http://llm:11434",
        ollama_model="qwen2.5:7b",
        comfyui_url="http://image:8188",
        comfyui_output_dir=root / "comfy-output",
        flux_workflow_path=root / "workflow.json",
        piper_executable=root / "piper",
        piper_model_path=root / "voice.onnx",
        ffmpeg_executable="ffmpeg",
        generated_dir=root / "portable-generated",
        database_url="sqlite+aiosqlite:///test.db",
        youtube_token_path=root / "youtube-token.json",
        youtube_client_secret_path=root / "client-secret.json",
    )


def test_image_cache_uses_generated_dir():
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        config = build_config(root)

        cache = ImageCache(
            runtime_config=config
        )

        expected = (
            config.generated_dir
            / "images"
            / "cache"
        )

        assert cache.cache == expected
        assert expected.is_dir()


def test_production_package_uses_generated_dir():
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        config = build_config(root)

        builder = ProductionPackageBuilder(
            runtime_config=config
        )

        expected = (
            config.generated_dir
            / "packages"
        )

        assert builder.base_dir == expected
        assert expected.is_dir()

        assert (
            builder.voice.output_dir
            == config.generated_dir / "audio"
        )


def test_defaults_remain_compatible():
    config = RuntimeConfig.from_environment()

    cache = ImageCache(
        runtime_config=config
    )

    builder = ProductionPackageBuilder(
        runtime_config=config
    )

    assert cache.cache == (
        Path(config.generated_dir)
        / "images"
        / "cache"
    )

    assert builder.base_dir == (
        Path(config.generated_dir)
        / "packages"
    )


def main():

    test_image_cache_uses_generated_dir()

    print(
        "PASS: image cache follows generated storage root."
    )

    test_production_package_uses_generated_dir()

    print(
        "PASS: production packages follow generated storage root."
    )

    test_defaults_remain_compatible()

    print(
        "PASS: current local defaults remain compatible."
    )

    print()

    print(
        "PASS: generated storage portability suite complete."
    )


if __name__ == "__main__":
    main()
