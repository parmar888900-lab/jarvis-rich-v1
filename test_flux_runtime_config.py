"""FLUX runtime configuration regression tests."""

import asyncio
import json
import tempfile
from pathlib import Path

from backend.services.image_generation.flux_provider import (
    FluxProvider,
)
from backend.services.runtime.runtime_config import (
    RuntimeConfig,
)


def build_config(
    root: Path,
) -> RuntimeConfig:
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
        json.dumps(
            {
                "41": {
                    "inputs": {
                        "clip_l": "",
                        "t5xxl": "",
                    }
                },
                "31": {
                    "inputs": {
                        "seed": 1,
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    return RuntimeConfig(
        ollama_base_url="http://llm:11434",
        ollama_model="qwen2.5:7b",
        comfyui_url="http://image-service:8188/",
        comfyui_output_dir=comfy_output,
        flux_workflow_path=workflow,
        piper_executable=(
            root
            / "piper"
        ),
        piper_model_path=(
            root
            / "voice.onnx"
        ),
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


def test_constructor_uses_runtime_config():
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)

        config = build_config(root)

        provider = FluxProvider(
            runtime_config=config
        )

        assert (
            provider.comfyui_url
            == "http://image-service:8188"
        )

        assert (
            provider.comfyui_output_dir
            == root / "comfy-output"
        )

        assert (
            provider.workflow_path
            == root / "flux.json"
        )

        assert (
            provider.jarvis_output_dir
            == root / "generated" / "images"
        )

        assert (
            provider.jarvis_output_dir.is_dir()
        )


def test_workflow_load_uses_configured_path():
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)

        provider = FluxProvider(
            runtime_config=build_config(root)
        )

        workflow = provider._load_workflow()

        assert "41" in workflow
        assert "31" in workflow


def test_prompt_injection_preserved():
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)

        provider = FluxProvider(
            runtime_config=build_config(root)
        )

        workflow = provider._load_workflow()

        provider._inject_prompt(
            workflow,
            "portable flux prompt",
        )

        assert (
            workflow["41"]["inputs"]["clip_l"]
            == "portable flux prompt"
        )

        assert (
            workflow["41"]["inputs"]["t5xxl"]
            == "portable flux prompt"
        )

        assert isinstance(
            workflow["31"]["inputs"]["seed"],
            int,
        )


def test_default_constructor_preserves_dev_defaults():
    provider = FluxProvider()

    assert (
        provider.comfyui_url
        == "http://127.0.0.1:8188"
    )

    assert (
        provider.workflow_path
        == Path(
            "configs/workflows/flux_api.json"
        )
    )

    assert (
        provider.comfyui_output_dir
        == Path(
            r"C:\Users\hp\ComfyUI\output"
        )
    )

    assert (
        provider.jarvis_output_dir
        == Path(
            "generated/images"
        )
    )


def main():
    test_constructor_uses_runtime_config()
    print(
        "PASS: FLUX constructor uses portable runtime configuration."
    )

    test_workflow_load_uses_configured_path()
    print(
        "PASS: FLUX workflow path is runtime-configurable."
    )

    test_prompt_injection_preserved()
    print(
        "PASS: FLUX prompt injection behavior is preserved."
    )

    test_default_constructor_preserves_dev_defaults()
    print(
        "PASS: FLUX development defaults remain unchanged."
    )

    print()
    print(
        "PASS: FLUX runtime configuration regression suite complete."
    )


if __name__ == "__main__":
    main()
