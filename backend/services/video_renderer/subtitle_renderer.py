"""
Subtitle rendering utilities for Jarvis videos.
"""

from moviepy import TextClip


class SubtitleRenderer:

    FONT_SIZE = 72
    WIDTH = 900

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

        if not text.strip():
            raise ValueError(
                "Subtitle text cannot be empty."
            )

        clip = TextClip(
            text=text.strip(),
            font_size=self.FONT_SIZE,
            method="caption",
            size=(self.WIDTH, None),
            text_align="center",
        )

        clip = (
            clip
            .with_start(start_time)
            .with_duration(duration)
            .with_position(
                (
                    "center",
                    1450,
                )
            )
        )

        return clip
