"""MoviePy / FFmpeg runtime configuration regressions."""

import tempfile
from pathlib import Path

from backend.services.runtime.runtime_config import RuntimeConfig
from backend.services.video_renderer.moviepy_runtime import (
    configure_moviepy_ffmpeg,
    moviepy_ffmpeg_bindings,
    resolve_ffmpeg_executable,
)


def build_config(
    root: Path,
    ffmpeg_executable: str,
) -> RuntimeConfig:

    comfy_output = root / "comfy"
    comfy_output.mkdir(
        parents=True,
        exist_ok=True,
    )

    workflow = root / "flux.json"
    workflow.write_text(
        "{}",
        encoding="utf-8",
    )

    piper = root / "piper"
    piper.write_text(
        "fake",
        encoding="utf-8",
    )

    model = root / "voice.onnx"
    model.write_text(
        "fake",
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
        ffmpeg_executable=ffmpeg_executable,
        generated_dir=root / "generated",
        database_url="",
        youtube_token_path=root / "token.json",
        youtube_client_secret_path=root / "client.json",
    )


def test_resolve_current_ffmpeg():
    executable = resolve_ffmpeg_executable(
        "ffmpeg"
    )

    assert executable

    assert Path(
        executable
    ).is_file()


def test_missing_ffmpeg_fails():
    missing = (
        "jarvis-definitely-missing-"
        "ffmpeg-binary-12345"
    )

    try:
        resolve_ffmpeg_executable(
            missing
        )
    except FileNotFoundError as exc:
        assert missing in str(
            exc
        )
    else:
        raise AssertionError(
            "Missing FFmpeg should fail."
        )


def test_moviepy_cached_bindings_are_synchronized():
    executable = configure_moviepy_ffmpeg(
        "ffmpeg"
    )

    bindings = moviepy_ffmpeg_bindings()

    expected_modules = {
        "moviepy.config",
        "moviepy.video.io.ffmpeg_reader",
        "moviepy.video.io.ffmpeg_tools",
        "moviepy.video.io.ffmpeg_writer",
        "moviepy.audio.io.ffmpeg_audiowriter",
        "moviepy.audio.io.readers",
    }

    assert set(
        bindings
    ) == expected_modules

    for module_name, value in bindings.items():
        assert (
            value
            == executable
        ), (
            module_name,
            value,
            executable,
        )


def test_video_renderer_uses_runtime_config():

    # Import after the adapter tests so this also exercises
    # already-imported MoviePy modules.
    from backend.services.video_renderer.renderer import (
        VideoRenderer,
    )

    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)

        resolved = resolve_ffmpeg_executable(
            "ffmpeg"
        )

        config = build_config(
            root,
            resolved,
        )

        renderer = VideoRenderer(
            runtime_config=config
        )

        assert (
            Path(renderer.output_dir)
            == root
            / "generated"
            / "videos"
        )

        assert (
            renderer.ffmpeg_executable
            == resolved
        )

        assert renderer.output_dir.is_dir()

        bindings = moviepy_ffmpeg_bindings()

        assert all(
            value == resolved
            for value in bindings.values()
        )


def test_default_renderer_preserves_dev_contract():

    from backend.services.video_renderer.renderer import (
        VideoRenderer,
    )

    renderer = VideoRenderer()

    assert (
        renderer.output_dir
        == Path(
            "generated/videos"
        )
    )

    assert renderer.ffmpeg_executable


def main():

    test_resolve_current_ffmpeg()

    print(
        "PASS: configured FFmpeg command resolves."
    )

    test_missing_ffmpeg_fails()

    print(
        "PASS: missing FFmpeg fails clearly."
    )

    test_moviepy_cached_bindings_are_synchronized()

    print(
        "PASS: all MoviePy cached FFmpeg bindings synchronize."
    )

    test_video_renderer_uses_runtime_config()

    print(
        "PASS: VideoRenderer consumes portable runtime configuration."
    )

    test_default_renderer_preserves_dev_contract()

    print(
        "PASS: VideoRenderer development defaults remain compatible."
    )

    print()
    print(
        "PASS: FFmpeg runtime configuration regression suite complete."
    )


if __name__ == "__main__":
    main()
