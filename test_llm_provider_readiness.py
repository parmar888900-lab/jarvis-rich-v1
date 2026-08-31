import tempfile
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from backend.services.runtime.capabilities import (
    Capability,
    RuntimeCapabilityService,
)
from backend.services.runtime.runtime_config import (
    RuntimeConfig,
)


def make_config(
    root: Path,
) -> RuntimeConfig:

    comfy = root / "comfy"
    comfy.mkdir()

    workflow = root / "workflow.json"
    workflow.write_text(
        "{}",
        encoding="utf-8",
    )

    piper = root / "piper.exe"
    piper.write_bytes(b"fake")

    voice = root / "voice.onnx"
    voice.write_bytes(b"fake")

    token = root / "youtube_token.json"
    token.write_text(
        "{}",
        encoding="utf-8",
    )

    generated = root / "generated"
    generated.mkdir()

    return RuntimeConfig(
        ollama_base_url="http://ollama:11434",
        ollama_model="qwen2.5:7b",
        comfyui_url="http://comfyui:8188",
        comfyui_output_dir=comfy,
        flux_workflow_path=workflow,
        piper_executable=piper,
        piper_model_path=voice,
        ffmpeg_executable="ffmpeg",
        generated_dir=generated,
        database_url="sqlite:///test.db",
        youtube_token_path=token,
        youtube_client_secret_path=(
            root / "unused.json"
        ),
        image_provider="comfyui",
        cloudflare_account_id="account",
        cloudflare_api_token="token",
        cloudflare_flux_model=(
            "@cf/black-forest-labs/"
            "flux-1-schnell"
        ),
        llm_provider="ollama",
        cloudflare_llm_model=(
            "@cf/meta/"
            "llama-3.1-8b-instruct-fast"
        ),
    )


def fake_module(
    *,
    name,
    module,
    required,
):
    return Capability(
        name=name,
        available=True,
        required_for_production=required,
        detail=f"fake module: {module}",
    )


def fake_command(
    *,
    name,
    command,
    required,
):
    return Capability(
        name=name,
        available=True,
        required_for_production=required,
        detail=f"fake command: {command}",
    )


def inspect(config):

    service = RuntimeCapabilityService(
        config
    )

    with (
        patch.object(
            RuntimeCapabilityService,
            "_python_module",
            side_effect=fake_module,
        ),
        patch.object(
            RuntimeCapabilityService,
            "_command",
            side_effect=fake_command,
        ),
    ):
        return service.inspect()


def test_cloudflare_llm_does_not_require_ollama():

    with tempfile.TemporaryDirectory() as temp:

        root = Path(temp)

        config = replace(
            make_config(root),
            llm_provider="cloudflare",
            ollama_base_url="",
            ollama_model="",
        )

        report = inspect(config)

        assert report.production_ready

        assert (
            "ollama"
            not in report.missing_required
        )

        assert (
            "ollama_model"
            not in report.missing_required
        )

        print(
            "PASS: Cloudflare LLM mode does not "
            "require local Ollama."
        )


def test_cloudflare_llm_requires_credentials():

    with tempfile.TemporaryDirectory() as temp:

        root = Path(temp)

        config = replace(
            make_config(root),
            llm_provider="cloudflare",
            cloudflare_account_id="",
            cloudflare_api_token="",
        )

        report = inspect(config)

        assert not report.production_ready

        assert (
            "cloudflare_account_id"
            in report.missing_required
        )

        assert (
            "cloudflare_api_token"
            in report.missing_required
        )

        print(
            "PASS: Cloudflare LLM requires "
            "Cloudflare credentials."
        )


def test_cloudflare_llm_requires_model():

    with tempfile.TemporaryDirectory() as temp:

        root = Path(temp)

        config = replace(
            make_config(root),
            llm_provider="cloudflare",
            cloudflare_llm_model="",
        )

        report = inspect(config)

        assert not report.production_ready

        assert (
            "cloudflare_llm_model"
            in report.missing_required
        )

        print(
            "PASS: Cloudflare LLM requires "
            "configured model."
        )


def test_ollama_still_required_locally():

    with tempfile.TemporaryDirectory() as temp:

        root = Path(temp)

        config = replace(
            make_config(root),
            llm_provider="ollama",
            ollama_base_url="",
        )

        report = inspect(config)

        assert not report.production_ready

        assert (
            "ollama"
            in report.missing_required
        )

        print(
            "PASS: Ollama mode still requires "
            "local Ollama."
        )


def test_unknown_llm_provider_fails_closed():

    with tempfile.TemporaryDirectory() as temp:

        root = Path(temp)

        config = replace(
            make_config(root),
            llm_provider="unknown",
        )

        report = inspect(config)

        assert not report.production_ready

        assert (
            "llm_provider"
            in report.missing_required
        )

        print(
            "PASS: unsupported LLM provider "
            "fails closed."
        )


def test_cloudflare_live_skips_ollama_probe():

    with tempfile.TemporaryDirectory() as temp:

        root = Path(temp)

        config = replace(
            make_config(root),
            llm_provider="cloudflare",
        )

        service = RuntimeCapabilityService(
            config
        )

        with (
            patch.object(
                RuntimeCapabilityService,
                "_python_module",
                side_effect=fake_module,
            ),
            patch.object(
                RuntimeCapabilityService,
                "_command",
                side_effect=fake_command,
            ),
            patch(
                "backend.services.runtime."
                "capabilities.ProviderHealthService."
                "probe_ollama"
            ) as ollama_probe,
            patch(
                "backend.services.runtime."
                "capabilities.ProviderHealthService."
                "probe_comfyui",
                return_value=(
                    __import__(
                        "backend.services.runtime."
                        "provider_health",
                        fromlist=["ProviderHealth"],
                    ).ProviderHealth(
                        name="comfyui",
                        available=True,
                        detail="fake healthy ComfyUI",
                    )
                ),
            ),
        ):
            report = service.inspect_live()

        ollama_probe.assert_not_called()

        assert report.production_ready

        print(
            "PASS: Cloudflare live readiness "
            "skips Ollama network probe."
        )


def main():

    test_cloudflare_llm_does_not_require_ollama()
    test_cloudflare_llm_requires_credentials()
    test_cloudflare_llm_requires_model()
    test_ollama_still_required_locally()
    test_unknown_llm_provider_fails_closed()
    test_cloudflare_live_skips_ollama_probe()

    print(
        "\nPASS: LLM-provider-aware readiness "
        "regression suite complete."
    )


if __name__ == "__main__":
    main()
