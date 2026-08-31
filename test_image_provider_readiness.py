import tempfile
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from backend.services.runtime.capabilities import (
    RuntimeCapabilityService,
)
from backend.services.runtime.provider_health import (
    ProviderHealth,
)
from backend.services.runtime.runtime_config import (
    RuntimeConfig,
)


def make_ready_config(
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
            root / "unused-secret.json"
        ),
        image_provider="comfyui",
    )


def fake_module(
    *,
    name,
    module,
    required,
):
    from backend.services.runtime.capabilities import (
        Capability,
    )

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
    from backend.services.runtime.capabilities import (
        Capability,
    )

    return Capability(
        name=name,
        available=True,
        required_for_production=required,
        detail=f"fake command: {command}",
    )


def test_cloudflare_does_not_require_comfyui():

    with tempfile.TemporaryDirectory() as temp:

        root = Path(temp)

        base = make_ready_config(
            root
        )

        config = replace(
            base,
            image_provider="cloudflare",
            cloudflare_account_id=(
                "fake-account"
            ),
            cloudflare_api_token=(
                "fake-token"
            ),
            cloudflare_flux_model=(
                "@cf/black-forest-labs/"
                "flux-1-schnell"
            ),
            comfyui_url="",
            comfyui_output_dir=(
                root / "missing-comfy"
            ),
            flux_workflow_path=(
                root / "missing-workflow.json"
            ),
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
        ):
            report = service.inspect()

        assert report.production_ready

        assert (
            "comfyui"
            not in report.missing_required
        )

        assert (
            "comfyui_output_dir"
            not in report.missing_required
        )

        assert (
            "flux_workflow"
            not in report.missing_required
        )

        print(
            "PASS: Cloudflare mode does not "
            "require local ComfyUI."
        )


def test_cloudflare_credentials_required():

    with tempfile.TemporaryDirectory() as temp:

        root = Path(temp)

        base = make_ready_config(
            root
        )

        config = replace(
            base,
            image_provider="cloudflare",
            cloudflare_account_id="",
            cloudflare_api_token="",
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
        ):
            report = service.inspect()

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
            "PASS: Cloudflare credentials "
            "are required in cloud mode."
        )


def test_comfyui_still_requires_local_assets():

    with tempfile.TemporaryDirectory() as temp:

        root = Path(temp)

        base = make_ready_config(
            root
        )

        config = replace(
            base,
            comfyui_output_dir=(
                root / "missing"
            ),
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
        ):
            report = service.inspect()

        assert not report.production_ready

        assert (
            "comfyui_output_dir"
            in report.missing_required
        )

        print(
            "PASS: ComfyUI mode still "
            "requires local assets."
        )


def test_unknown_provider_fails_closed():

    with tempfile.TemporaryDirectory() as temp:

        root = Path(temp)

        config = replace(
            make_ready_config(root),
            image_provider="unknown",
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
        ):
            report = service.inspect()

        assert not report.production_ready

        assert (
            "image_provider"
            in report.missing_required
        )

        print(
            "PASS: unsupported image provider "
            "fails closed."
        )


def test_cloudflare_live_skips_comfyui_probe():

    with tempfile.TemporaryDirectory() as temp:

        root = Path(temp)

        config = replace(
            make_ready_config(root),
            image_provider="cloudflare",
            cloudflare_account_id=(
                "fake-account"
            ),
            cloudflare_api_token=(
                "fake-token"
            ),
        )

        service = RuntimeCapabilityService(
            config
        )

        healthy_ollama = ProviderHealth(
            name="ollama",
            available=True,
            detail="fake healthy Ollama",
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
                "probe_ollama",
                return_value=healthy_ollama,
            ),
            patch(
                "backend.services.runtime."
                "capabilities.ProviderHealthService."
                "probe_comfyui"
            ) as comfy_probe,
        ):
            report = service.inspect_live()

        comfy_probe.assert_not_called()

        assert report.production_ready

        print(
            "PASS: Cloudflare live readiness "
            "skips ComfyUI network probe."
        )


def main():

    test_cloudflare_does_not_require_comfyui()
    test_cloudflare_credentials_required()
    test_comfyui_still_requires_local_assets()
    test_unknown_provider_fails_closed()
    test_cloudflare_live_skips_comfyui_probe()

    print(
        "\nPASS: image-provider-aware readiness "
        "regression suite complete."
    )


if __name__ == "__main__":
    main()
