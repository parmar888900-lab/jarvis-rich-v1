"""Reference-timed luxury benchmark renderer for Jarvis Rich V1."""

from __future__ import annotations

from pathlib import Path

from moviepy import (
    VideoFileClip,
    concatenate_videoclips,
)

from backend.services.runtime.runtime_config import RuntimeConfig
from backend.services.video.luxury_reference_timeline import (
    LuxuryReferenceTimeline,
)
from backend.services.video.source_clip_indexer import (
    IndexedSourceClip,
)
from backend.services.video_renderer.moviepy_runtime import (
    configure_moviepy_ffmpeg,
)


class LuxuryBenchmarkRenderer:
    """
    Build the first output-first Rich V1 luxury benchmark.

    Uses:
        - real luxury/product source footage
        - exact 11756 benchmark cut timings
        - vertical 1080x2400 framing
        - 60 fps
        - mild reference-style punch-ins
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
        indexed_clips: list[IndexedSourceClip],
    ) -> dict:

        timeline = (
            LuxuryReferenceTimeline.shots()
        )

        if len(indexed_clips) < len(timeline):
            raise RuntimeError(
                "Luxury benchmark needs at least "
                f"{len(timeline)} indexed clips; "
                f"received {len(indexed_clips)}."
            )

        ####################################################
        # Spread selections across the source instead of
        # consuming only the first 30 clips.
        ####################################################

        selected = self._spread_select(
            indexed_clips,
            count=len(timeline),
        )

        rendered_clips = []
        opened_sources = []

        try:

            for shot, indexed in zip(
                timeline,
                selected,
            ):

                source_path = Path(
                    indexed.source_path
                )

                if not source_path.exists():
                    raise FileNotFoundError(
                        source_path
                    )

                source = VideoFileClip(
                    str(source_path)
                )

                opened_sources.append(
                    source
                )

                target_duration = float(
                    shot.duration
                )

                ################################################
                # Start from the indexed semantically useful
                # moment but allow longer benchmark shots to
                # continue through the original source.
                ################################################

                start = max(
                    0.0,
                    float(
                        indexed.start_time
                    ),
                )

                if (
                    start + target_duration
                    > source.duration
                ):
                    start = max(
                        0.0,
                        source.duration
                        - target_duration
                    )

                end = min(
                    source.duration,
                    start + target_duration,
                )

                actual_duration = (
                    end - start
                )

                if actual_duration <= 0:
                    continue

                clip = source.subclipped(
                    start,
                    end,
                )

                ################################################
                # Fill the 1080x2400 reference canvas.
                ################################################

                scale = max(
                    LuxuryReferenceTimeline.WIDTH
                    / clip.w,
                    LuxuryReferenceTimeline.HEIGHT
                    / clip.h,
                )

                clip = clip.resized(
                    scale
                )

                ################################################
                # Controlled punch-in rhythm.
                #
                # This is deliberately subtle for premium
                # product footage.
                ################################################

                pattern = (
                    1.00,
                    1.035,
                    1.00,
                    1.055,
                    1.02,
                )

                zoom = pattern[
                    (shot.index - 1)
                    % len(pattern)
                ]

                if zoom != 1.0:
                    clip = clip.resized(
                        zoom
                    )

                clip = clip.cropped(
                    x_center=(
                        clip.w / 2
                    ),
                    y_center=(
                        clip.h / 2
                    ),
                    width=(
                        LuxuryReferenceTimeline.WIDTH
                    ),
                    height=(
                        LuxuryReferenceTimeline.HEIGHT
                    ),
                )

                clip = clip.with_duration(
                    actual_duration
                )

                rendered_clips.append(
                    clip
                )

            if not rendered_clips:
                raise RuntimeError(
                    "Luxury benchmark produced no clips."
                )

            final = concatenate_videoclips(
                rendered_clips,
                method="compose",
            )

            safe_name = "".join(
                character
                if character.isalnum()
                else "_"
                for character in title
            )[:70]

            output = (
                self.output_dir
                / (
                    f"{safe_name}_"
                    "luxury_benchmark_v1.mp4"
                )
            )

            final.write_videofile(
                str(output),
                fps=(
                    LuxuryReferenceTimeline.FPS
                ),
                codec="libx264",
                audio_codec="aac",
                logger=None,
            )

            result = {
                "status": "success",
                "video_path": str(output),
                "shot_count": len(
                    rendered_clips
                ),
                "duration": round(
                    float(
                        final.duration
                    ),
                    3,
                ),
                "resolution": (
                    f"{LuxuryReferenceTimeline.WIDTH}"
                    f"x{LuxuryReferenceTimeline.HEIGHT}"
                ),
                "fps": (
                    LuxuryReferenceTimeline.FPS
                ),
                "benchmark": (
                    LuxuryReferenceTimeline.REFERENCE_NAME
                ),
            }

            final.close()

            return result

        finally:

            for clip in rendered_clips:

                try:
                    clip.close()
                except Exception:
                    pass

            for source in opened_sources:

                try:
                    source.close()
                except Exception:
                    pass

    @staticmethod
    def _spread_select(
        clips: list[IndexedSourceClip],
        *,
        count: int,
    ) -> list[IndexedSourceClip]:

        if count <= 0:
            return []

        if len(clips) < count:
            raise RuntimeError(
                "Not enough indexed clips."
            )

        if count == 1:
            return [
                clips[
                    len(clips) // 2
                ]
            ]

        indexes = []

        for position in range(count):

            ratio = (
                position
                / (
                    count - 1
                )
            )

            index = round(
                ratio
                * (
                    len(clips) - 1
                )
            )

            indexes.append(
                index
            )

        return [
            clips[index]
            for index in indexes
        ]
