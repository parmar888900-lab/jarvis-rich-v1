"""Render semantically matched source clips for Jarvis Rich V1."""

from __future__ import annotations

from pathlib import Path

from moviepy import (
    VideoFileClip,
    concatenate_videoclips,
)

from backend.services.runtime.runtime_config import RuntimeConfig
from backend.services.video.clip_matcher import MatchedClip
from backend.services.video.reference_profiles import RichFormatProfile
from backend.services.video_renderer.moviepy_runtime import (
    configure_moviepy_ffmpeg,
)


class MatchedClipRenderer:
    """
    Render exact source segments selected by ClipMatcher.

    Unlike the old renderer, this does not choose arbitrary portions
    of a MediaAsset. It honors the indexed source timestamps.
    """

    def __init__(
        self,
        runtime_config: RuntimeConfig | None = None,
    ) -> None:

        config = (
            runtime_config
            if runtime_config is not None
            else RuntimeConfig.from_environment()
        )

        self.ffmpeg_executable = (
            configure_moviepy_ffmpeg(
                config.ffmpeg_executable
            )
        )

        self.output_dir = (
            Path(config.generated_dir)
            / "videos"
        )

        self.output_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

    async def render(
        self,
        *,
        title: str,
        matches: list[MatchedClip],
        profile: RichFormatProfile,
    ) -> dict:

        if not matches:
            raise RuntimeError(
                "MatchedClipRenderer received no matched clips."
            )

        clips = []
        opened_sources = []

        try:

            for index, match in enumerate(
                matches
            ):

                source_path = Path(
                    match.source_path
                )

                if not source_path.exists():
                    continue

                source = VideoFileClip(
                    str(source_path)
                )

                opened_sources.append(
                    source
                )

                start = max(
                    0.0,
                    float(
                        match.start_time
                    ),
                )

                end = min(
                    float(
                        match.end_time
                    ),
                    float(
                        source.duration
                    ),
                )

                if end <= start:
                    continue

                clip = source.subclipped(
                    start,
                    end,
                )

                ################################################
                # Vertical 9:16 reframe.
                ################################################

                scale = max(
                    profile.width / clip.w,
                    profile.height / clip.h,
                )

                clip = clip.resized(
                    scale
                )

                ################################################
                # Light deterministic zoom variation.
                ################################################

                if (
                    profile.zoom_enabled
                    and index % 3 == 1
                ):
                    clip = clip.resized(
                        1.035
                    )

                elif (
                    profile.zoom_enabled
                    and index % 3 == 2
                ):
                    clip = clip.resized(
                        1.06
                    )

                clip = clip.cropped(
                    x_center=clip.w / 2,
                    y_center=clip.h / 2,
                    width=profile.width,
                    height=profile.height,
                )

                clips.append(
                    clip
                )

            if not clips:
                raise RuntimeError(
                    "No matched clips were renderable."
                )

            final = concatenate_videoclips(
                clips,
                method="compose",
            )

            safe_name = "".join(
                c if c.isalnum()
                else "_"
                for c in title
            )[:70]

            output = (
                self.output_dir
                / (
                    f"{safe_name}_"
                    f"{profile.format_name}_"
                    "matched.mp4"
                )
            )

            final.write_videofile(
                str(output),
                fps=profile.fps,
                codec="libx264",
                audio_codec="aac",
                logger=None,
            )

            duration = float(
                final.duration
            )

            final.close()

            return {
                "status": "success",
                "video_path": str(
                    output
                ),
                "format_name": (
                    profile.format_name
                ),
                "clip_count": len(
                    clips
                ),
                "duration": round(
                    duration,
                    2,
                ),
                "resolution": (
                    f"{profile.width}"
                    f"x{profile.height}"
                ),
                "fps": profile.fps,
            }

        finally:

            for clip in clips:

                try:
                    clip.close()
                except Exception:
                    pass

            for source in opened_sources:

                try:
                    source.close()
                except Exception:
                    pass
