"""
Subtitle rendering utilities for Jarvis videos.
"""

from moviepy import TextClip


class SubtitleRenderer:

    # Tuned for 1080x1920 vertical Shorts.
    FONT_SIZE = 96
    WIDTH = 920
    Y_POSITION = 1060

    TEXT_COLOR = "white"
    STROKE_COLOR = "black"
    STROKE_WIDTH = 7

    WORDS_PER_PHRASE = 3

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

    def create_phrase_clips(
        self,
        text: str,
        start_time: float,
        end_time: float,
    ) -> list[TextClip]:

        text = text.strip()

        if not text:
            raise ValueError(
                "Subtitle text cannot be empty."
            )

        duration = (
            end_time - start_time
        )

        if duration <= 0:
            raise ValueError(
                "Subtitle duration must be positive."
            )

        words = text.split()

        phrases = [
            words[
                index:
                index + self.WORDS_PER_PHRASE
            ]
            for index in range(
                0,
                len(words),
                self.WORDS_PER_PHRASE,
            )
        ]

        total_words = len(words)

        clips = []

        current_time = start_time

        for index, phrase_words in enumerate(
            phrases
        ):

            phrase_text = " ".join(
                phrase_words
            )

            phrase_duration = (
                duration
                * len(phrase_words)
                / total_words
            )

            # Force the final phrase to end exactly
            # at the scene boundary.
            if index == len(phrases) - 1:
                phrase_end = end_time
            else:
                phrase_end = (
                    current_time
                    + phrase_duration
                )

            clip = self.create_clip(
                text=phrase_text,
                start_time=current_time,
                end_time=phrase_end,
            )

            clips.append(
                clip
            )

            current_time = phrase_end

        return clips

