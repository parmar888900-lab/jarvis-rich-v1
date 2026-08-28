"""
Subtitle rendering utilities for Jarvis videos.
"""

from moviepy import TextClip


class SubtitleRenderer:

    # Tuned for 1080x1920 vertical Shorts.
    FONT_SIZE = 78
    WIDTH = 900
    Y_POSITION = 1320

    TEXT_COLOR = "white"
    STROKE_COLOR = "black"
    STROKE_WIDTH = 5

    def create_clip(
        self,
        text: str,
        start_time: float,
        end_time: float,
    ) -> TextClip:

        duration = (
            end_time - start_time
        )

        if duration <= 0:
            raise ValueError(
                "Subtitle duration must be positive."
            )

        text = text.strip()

        if not text:
            raise ValueError(
                "Subtitle text cannot be empty."
            )

        clip = TextClip(
            text=text,
            font_size=self.FONT_SIZE,
            color=self.TEXT_COLOR,
            stroke_color=self.STROKE_COLOR,
            stroke_width=self.STROKE_WIDTH,
            method="caption",
            size=(
                self.WIDTH,
                None,
            ),
            text_align="center",
        )

        return (
            clip
            .with_start(
                start_time
            )
            .with_duration(
                duration
            )
            .with_position(
                (
                    "center",
                    self.Y_POSITION,
                )
            )
        )
