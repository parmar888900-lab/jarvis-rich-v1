"""Vertical movie-clip renderer for licensed/public-domain footage."""

from __future__ import annotations

from pathlib import Path

from moviepy import (
    CompositeVideoClip,
    TextClip,
    VideoFileClip,
    concatenate_videoclips,
)

from backend.services.runtime.runtime_config import RuntimeConfig
from backend.services.video.media_asset import MediaAsset


class MovieClipRenderer:

    WIDTH = 1080
    HEIGHT = 1920
    FPS = 30

    TARGET_DURATION = 24.0
    SHOT_DURATION = 3.0

    CAPTION_Y = 1080
    CAPTION_WIDTH = 850
    CAPTION_FONT_SIZE = 72

    def __init__(
        self,
        runtime_config: RuntimeConfig | None = None,
    ) -> None:

        config = (
            runtime_config
            if runtime_config is not None
            else RuntimeConfig.from_environment()
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
        asset: MediaAsset,
        title: str,
        hook_text: str,
    ) -> dict:

        if asset.asset_type != "video":
            raise ValueError(
                "MovieClipRenderer requires a video asset."
            )

        source_path = Path(
            asset.file_path
        )

        if not source_path.is_file():
            raise FileNotFoundError(
                source_path
            )

        source = VideoFileClip(
            str(source_path)
        )

        clips = []
        final = None
        caption = None

        try:

            if source.duration <= 0:
                raise RuntimeError(
                    "Movie source has invalid duration."
                )

            target = min(
                self.TARGET_DURATION,
                float(source.duration),
            )

            ################################################
            # Select a segment away from opening titles
            ################################################

            available_start = max(
                0.0,
                source.duration - target,
            )

            start = min(
                max(
                    source.duration * 0.15,
                    0.0,
                ),
                available_start,
            )

            end = start + target

            ################################################
            # Split into short visual beats
            ################################################

            current = start
            shot_index = 0

            while current < end:

                shot_end = min(
                    current
                    + self.SHOT_DURATION,
                    end,
                )

                clip = source.subclipped(
                    current,
                    shot_end,
                )

                ################################################
                # Fill 9:16 vertically.
                ################################################

                scale = max(
                    self.WIDTH / clip.w,
                    self.HEIGHT / clip.h,
                )

                clip = clip.resized(
                    scale
                )

                clip = clip.cropped(
                    x_center=clip.w / 2,
                    y_center=clip.h / 2,
                    width=self.WIDTH,
                    height=self.HEIGHT,
                )

                ################################################
                # Alternate framing slightly between cuts.
                ################################################

                if shot_index % 2 == 1:
                    clip = clip.resized(
                        1.04
                    )

                    clip = clip.cropped(
                        x_center=clip.w / 2,
                        y_center=clip.h / 2,
                        width=self.WIDTH,
                        height=self.HEIGHT,
                    )

                clips.append(
                    clip
                )

                shot_index += 1
                current = shot_end

            if not clips:
                raise RuntimeError(
                    "Movie renderer produced no shots."
                )

            base = concatenate_videoclips(
                clips,
                method="compose",
            )

            ################################################
            # Hook caption in Shorts-safe zone
            ################################################

            caption = (
                TextClip(
                    text=hook_text,
                    font_size=self.CAPTION_FONT_SIZE,
                    color="white",
                    stroke_color="black",
                    stroke_width=5,
                    method="caption",
                    size=(
                        self.CAPTION_WIDTH,
                        None,
                    ),
                    text_align="center",
                )
                .with_start(0)
                .with_duration(
                    min(
                        4.0,
                        base.duration,
                    )
                )
                .with_position(
                    (
                        "center",
                        self.CAPTION_Y,
                    )
                )
            )

            final = CompositeVideoClip(
                [
                    base,
                    caption,
                ],
                size=(
                    self.WIDTH,
                    self.HEIGHT,
                ),
            )

            safe_name = "".join(
                c if c.isalnum()
                else "_"
                for c in title
            )[:60]

            output = (
                self.output_dir
                / f"{safe_name}_movie_short.mp4"
            )

            final.write_videofile(
                str(output),
                fps=self.FPS,
                codec="libx264",
                audio_codec="aac",
                logger=None,
            )

            return {
                "status": "success",
                "video_path": str(output),
                "duration": final.duration,
                "source_url": asset.source_url,
                "license_name": asset.license_name,
                "creator": asset.creator,
                "resolution": (
                    f"{self.WIDTH}x{self.HEIGHT}"
                ),
            }

        finally:

            if final is not None:
                final.close()

            if caption is not None:
                caption.close()

            for clip in clips:
                clip.close()

            source.close()
