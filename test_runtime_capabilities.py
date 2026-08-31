"""Runtime capability regression tests."""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

from backend.services.runtime.capabilities import (
    RuntimeCapabilityService,
)
from backend.services.runtime.runtime_config import (
    RuntimeConfig,
)


def build_config(
    root: Path,
) -> RuntimeConfig:
    comfy = (
        root
        / "comfy-output"
    )

    comfy.mkdir()

    workflow = (
        root
        / "workflow.json"
    )

    workflow.write_text(
        "{}",
        encoding="utf-8",
    )

    piper = (
        root
        / "piper"
    )

    piper.write_text(
        "fake",
        encoding="utf-8",
    )

    model = (
        root
        / "voice.onnx"
    )

    model.write_text(
        "fake",
        encoding="utf-8",
    )

    token = (
        root
        / "youtube-token.json"
    )

    token.write_text(
        "{}",
        encoding="utf-8",
    )

    return RuntimeConfig(
        ollama_base_url=(
            "http://localhost:11434"
        ),
        ollama_model="qwen2.5:7b",
        comfyui_url=(
            "http://localhost:8188"
        ),
        comfyui_output_dir=comfy,
        flux_workflow_path=workflow,
        piper_executable=piper,
        piper_model_path=model,
        ffmpeg_executable="ffmpeg",
        generated_dir=(
            root
            / "generated"
        ),
        database_url=(
            "sqlite+aiosqlite:///test.db"
        ),
        youtube_token_path=token,
        youtube_client_secret_path=(
            root
            / "optional-client-secret.json"
        ),
    )


def test_ready_machine_reports_ready():
    with tempfile.TemporaryDirectory() as temp:
        root = Path(
            temp
        )

        config = build_config(
            root
        )

        service = RuntimeCapabilityService(
            config
        )

        with patch(
            "backend.services.runtime.capabilities."
            "shutil.which",
            return_value="/usr/bin/ffmpeg",
        ), patch(
            "backend.services.runtime.capabilities."
            "importlib.util.find_spec",
            return_value=object(),
        ):
            report = service.inspect()

        assert report.production_ready
        assert report.missing_required == ()


def test_missing_ffmpeg_blocks_production():
    with tempfile.TemporaryDirectory() as temp:
        root = Path(
            temp
        )

        service = RuntimeCapabilityService(
            build_config(
                root
            )
        )

        with patch(
            "backend.services.runtime.capabilities."
            "shutil.which",
            return_value=None,
        ), patch(
            "backend.services.runtime.capabilities."
            "importlib.util.find_spec",
            return_value=object(),
        ):
            report = service.inspect()

        assert not report.production_ready
        assert "ffmpeg" in report.missing_required


def test_missing_youtube_token_blocks_production():
    with tempfile.TemporaryDirectory() as temp:
        root = Path(
            temp
        )

        config = build_config(
            root
        )

        config.youtube_token_path.unlink()

        service = RuntimeCapabilityService(
            config
        )

        with patch(
            "backend.services.runtime.capabilities."
            "shutil.which",
            return_value="/usr/bin/ffmpeg",
        ), patch(
            "backend.services.runtime.capabilities."
            "importlib.util.find_spec",
            return_value=object(),
        ):
            report = service.inspect()

        assert not report.production_ready

        assert (
            "youtube_token"
            in report.missing_required
        )


def test_client_secret_is_not_runtime_required():
    with tempfile.TemporaryDirectory() as temp:
        root = Path(
            temp
        )

        service = RuntimeCapabilityService(
            build_config(
                root
            )
        )

        with patch(
            "backend.services.runtime.capabilities."
            "shutil.which",
            return_value="/usr/bin/ffmpeg",
        ), patch(
            "backend.services.runtime.capabilities."
            "importlib.util.find_spec",
            return_value=object(),
        ):
            report = service.inspect()

        client_secret = next(
            item
            for item
            in report.capabilities
            if item.name
            == "youtube_client_secret"
        )

        assert not client_secret.available

        assert (
            not client_secret
            .required_for_production
        )

        assert report.production_ready


def test_environment_overrides_are_portable():
    values = {
        "JARVIS_OLLAMA_BASE_URL":
            "http://llm:11434",
        "JARVIS_OLLAMA_MODEL":
            "qwen-cloud",
        "JARVIS_COMFYUI_URL":
            "http://image:8188",
        "JARVIS_COMFYUI_OUTPUT_DIR":
            "/srv/comfy/output",
        "JARVIS_FLUX_WORKFLOW_PATH":
            "/srv/jarvis/flux.json",
        "JARVIS_PIPER_EXECUTABLE":
            "/usr/local/bin/piper",
        "JARVIS_PIPER_MODEL_PATH":
            "/srv/models/voice.onnx",
        "JARVIS_FFMPEG_EXECUTABLE":
            "/usr/bin/ffmpeg",
        "JARVIS_GENERATED_DIR":
            "/srv/jarvis/generated",
        "JARVIS_DATABASE_URL":
            "sqlite+aiosqlite:///data/jarvis.db",
        "JARVIS_YOUTUBE_TOKEN_PATH":
            "/run/secrets/youtube-token.json",
    }

    with patch.dict(
        os.environ,
        values,
        clear=False,
    ):
        config = (
            RuntimeConfig
            .from_environment()
        )

    assert (
        config.ollama_base_url
        == "http://llm:11434"
    )

    assert (
        config.comfyui_output_dir
        == Path(
            "/srv/comfy/output"
        )
    )

    assert (
        config.piper_executable
        == Path(
            "/usr/local/bin/piper"
        )
    )

    assert (
        config.ffmpeg_executable
        == "/usr/bin/ffmpeg"
    )

    assert (
        config.database_url
        == "sqlite+aiosqlite:///data/jarvis.db"
    )


def test_report_serializes_safely():
    with tempfile.TemporaryDirectory() as temp:
        root = Path(
            temp
        )

        service = RuntimeCapabilityService(
            build_config(
                root
            )
        )

        with patch(
            "backend.services.runtime.capabilities."
            "shutil.which",
            return_value="/usr/bin/ffmpeg",
        ), patch(
            "backend.services.runtime.capabilities."
            "importlib.util.find_spec",
            return_value=object(),
        ):
            result = (
                service
                .inspect()
                .as_dict()
            )

        assert (
            result["production_ready"]
            is True
        )

        assert (
            result["missing_required"]
            == []
        )

        assert isinstance(
            result["capabilities"],
            list,
        )


def main():
    test_ready_machine_reports_ready()
    print(
        "PASS: complete machine reports production-ready."
    )

    test_missing_ffmpeg_blocks_production()
    print(
        "PASS: missing FFmpeg blocks production readiness."
    )

    test_missing_youtube_token_blocks_production()
    print(
        "PASS: missing YouTube token blocks autonomous publishing."
    )

    test_client_secret_is_not_runtime_required()
    print(
        "PASS: OAuth client secret is not required after authorization."
    )

    test_environment_overrides_are_portable()
    print(
        "PASS: runtime provider configuration supports environment overrides."
    )

    test_report_serializes_safely()
    print(
        "PASS: capability report serializes safely."
    )

    print()
    print(
        "PASS: Runtime Capability regression suite complete."
    )


if __name__ == "__main__":
    main()
