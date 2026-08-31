"""Runtime configuration bridge for MoviePy FFmpeg execution."""

from __future__ import annotations

import importlib
import shutil
from pathlib import Path


_MOVIEPY_FFMPEG_MODULES = (
    "moviepy.config",
    "moviepy.video.io.ffmpeg_reader",
    "moviepy.video.io.ffmpeg_tools",
    "moviepy.video.io.ffmpeg_writer",
    "moviepy.audio.io.ffmpeg_audiowriter",
    "moviepy.audio.io.readers",
)


def resolve_ffmpeg_executable(
    value: str | Path,
) -> str:
    """Resolve an FFmpeg path or command without relying on MoviePy defaults."""

    raw = str(
        value
    ).strip()

    if not raw:
        raise ValueError(
            "FFmpeg executable is not configured."
        )

    path = Path(
        raw
    ).expanduser()

    # Explicit file path.
    if path.is_file():
        return str(
            path
        )

    # Command available through PATH.
    discovered = shutil.which(
        raw
    )

    if discovered is not None:
        return discovered

    raise FileNotFoundError(
        f"FFmpeg executable not found: {raw}"
    )


def configure_moviepy_ffmpeg(
    value: str | Path,
) -> str:
    """Configure every MoviePy module that caches FFMPEG_BINARY.

    MoviePy 2.1.x imports FFMPEG_BINARY by value into several reader
    and writer modules. Updating moviepy.config alone therefore does
    not update modules that are already imported.

    Jarvis uses one runtime FFmpeg configuration per process, so this
    function synchronizes all known MoviePy FFmpeg bindings.
    """

    executable = resolve_ffmpeg_executable(
        value
    )

    for module_name in _MOVIEPY_FFMPEG_MODULES:
        module = importlib.import_module(
            module_name
        )

        if hasattr(
            module,
            "FFMPEG_BINARY",
        ):
            module.FFMPEG_BINARY = executable

    return executable


def moviepy_ffmpeg_bindings() -> dict[str, str]:
    """Return MoviePy FFmpeg bindings for diagnostics/tests."""

    result: dict[str, str] = {}

    for module_name in _MOVIEPY_FFMPEG_MODULES:
        module = importlib.import_module(
            module_name
        )

        if hasattr(
            module,
            "FFMPEG_BINARY",
        ):
            result[module_name] = str(
                module.FFMPEG_BINARY
            )

    return result
