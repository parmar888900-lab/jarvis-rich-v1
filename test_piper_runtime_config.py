"""Piper runtime configuration regression tests."""

import asyncio
import tempfile
import wave
from pathlib import Path
from unittest.mock import AsyncMock, patch

from backend.services.runtime.runtime_config import (
    RuntimeConfig,
)
from backend.services.video.voice_generator import (
    VoiceGenerator,
)


def build_config(
    root: Path,
) -> RuntimeConfig:
    piper = (
        root
        / "bin"
        / "piper"
    )

    piper.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    piper.write_text(
        "fake executable",
        encoding="utf-8",
    )

    model = (
        root
        / "models"
        / "voice.onnx"
    )

    model.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    model.write_text(
        "fake model",
        encoding="utf-8",
    )

    comfy_output = (
        root
        / "comfy-output"
    )

    comfy_output.mkdir()

    workflow = (
        root
        / "flux.json"
    )

    workflow.write_text(
        "{}",
        encoding="utf-8",
    )

    return RuntimeConfig(
        ollama_base_url="http://llm:11434",
        ollama_model="qwen2.5:7b",
        comfyui_url="http://image:8188",
        comfyui_output_dir=comfy_output,
        flux_workflow_path=workflow,
        piper_executable=piper,
        piper_model_path=model,
        ffmpeg_executable="ffmpeg",
        generated_dir=(
            root
            / "generated"
        ),
        database_url="",
        youtube_token_path=(
            root
            / "token.json"
        ),
        youtube_client_secret_path=(
            root
            / "client.json"
        ),
    )


def create_test_wav(
    path: Path,
    *,
    frames: int = 16000,
    frame_rate: int = 16000,
) -> None:
    with wave.open(
        str(path),
        "wb",
    ) as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(
            frame_rate
        )
        wav.writeframes(
            b"\x00\x00"
            * frames
        )


def test_constructor_uses_runtime_config():
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)

        config = build_config(root)

        generator = VoiceGenerator(
            runtime_config=config
        )

        assert (
            generator.piper_executable
            == root / "bin" / "piper"
        )

        assert (
            generator.model_path
            == root / "models" / "voice.onnx"
        )

        assert (
            generator.output_dir
            == root / "generated" / "audio"
        )

        assert (
            generator.output_dir.is_dir()
        )


def test_default_constructor_preserves_dev_defaults():
    generator = VoiceGenerator()

    assert (
        generator.piper_executable
        == Path(
            "venv/Scripts/piper.exe"
        )
    )

    assert (
        generator.model_path
        == Path(
            "models/piper/"
            "en_GB-northern_english_"
            "male-medium.onnx"
        )
    )

    assert (
        generator.output_dir
        == Path(
            "generated/audio"
        )
    )


def test_validate_piper_uses_configured_paths():
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)

        generator = VoiceGenerator(
            runtime_config=build_config(root)
        )

        generator._validate_piper()


def test_validate_piper_accepts_path_command():
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)

        config = build_config(
            root
        )

        config = RuntimeConfig(
            ollama_base_url=config.ollama_base_url,
            ollama_model=config.ollama_model,
            comfyui_url=config.comfyui_url,
            comfyui_output_dir=config.comfyui_output_dir,
            flux_workflow_path=config.flux_workflow_path,
            piper_executable=Path("piper"),
            piper_model_path=config.piper_model_path,
            ffmpeg_executable=config.ffmpeg_executable,
            generated_dir=config.generated_dir,
            database_url=config.database_url,
            youtube_token_path=config.youtube_token_path,
            youtube_client_secret_path=(
                config.youtube_client_secret_path
            ),
        )

        generator = VoiceGenerator(
            runtime_config=config
        )

        with patch(
            "backend.services.video.voice_generator."
            "shutil.which",
            return_value="/usr/local/bin/piper",
        ):
            generator._validate_piper()


def test_missing_model_fails_cleanly():
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)

        config = build_config(root)

        config.piper_model_path.unlink()

        generator = VoiceGenerator(
            runtime_config=config
        )

        try:
            generator._validate_piper()
        except FileNotFoundError as exc:
            assert (
                "Piper model not found"
                in str(exc)
            )
        else:
            raise AssertionError(
                "Missing Piper model should fail."
            )


def test_missing_executable_fails_cleanly():
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)

        config = build_config(root)

        config.piper_executable.unlink()

        generator = VoiceGenerator(
            runtime_config=config
        )

        try:
            generator._validate_piper()
        except FileNotFoundError as exc:
            assert (
                "Piper executable not found"
                in str(exc)
            )
        else:
            raise AssertionError(
                "Missing Piper executable should fail."
            )


async def test_generate_preserves_contract():
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)

        generator = VoiceGenerator(
            runtime_config=build_config(root)
        )

        async def fake_run_piper(
            script: str,
            output_file: Path,
        ) -> None:
            assert (
                script
                == "Portable Piper test."
            )

            create_test_wav(
                output_file
            )

        with patch.object(
            generator,
            "_run_piper",
            new=fake_run_piper,
        ):
            result = await generator.generate(
                "Portable Piper test.",
                filename="portable-test",
            )

        assert (
            result["status"]
            == "success"
        )

        assert (
            result["provider"]
            == "piper"
        )

        assert (
            result["script"]
            == "Portable Piper test."
        )

        assert Path(
            result["audio_path"]
        ).is_file()

        assert (
            result["duration"]
            == 1.0
        )


def main():
    test_constructor_uses_runtime_config()
    print(
        "PASS: Piper constructor uses portable runtime configuration."
    )

    test_default_constructor_preserves_dev_defaults()
    print(
        "PASS: Piper development defaults remain unchanged."
    )

    test_validate_piper_uses_configured_paths()
    print(
        "PASS: Piper validation uses configured paths."
    )

    test_validate_piper_accepts_path_command()
    print(
        "PASS: Piper validation accepts a PATH command."
    )

    test_missing_model_fails_cleanly()
    print(
        "PASS: missing Piper model fails clearly."
    )

    test_missing_executable_fails_cleanly()
    print(
        "PASS: missing Piper executable fails clearly."
    )

    asyncio.run(
        test_generate_preserves_contract()
    )

    print(
        "PASS: Piper generation result contract remains unchanged."
    )

    print()
    print(
        "PASS: Piper runtime configuration regression suite complete."
    )


if __name__ == "__main__":
    main()
