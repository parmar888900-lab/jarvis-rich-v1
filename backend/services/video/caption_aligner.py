"""
Speech-aligned caption timing using OpenAI Whisper.
"""

import asyncio
from pathlib import Path

import whisper


class CaptionAligner:

    MODEL_NAME = "tiny.en"

    WORDS_PER_PHRASE = 3

    # Start a new caption when speech pauses
    # for at least this long.
    PAUSE_THRESHOLD = 0.24

    def __init__(self):

        self._model = None

    def _load_model(self):

        if self._model is None:

            self._model = whisper.load_model(
                self.MODEL_NAME
            )

        return self._model

    async def align(
        self,
        audio_path: str,
    ) -> list[dict]:

        path = Path(audio_path)

        if not path.exists():
            raise FileNotFoundError(
                f"Audio not found: {path}"
            )

        result = await asyncio.to_thread(
            self._transcribe,
            str(path),
        )

        words = []

        for segment in result.get(
            "segments",
            []
        ):

            for word in segment.get(
                "words",
                []
            ):

                text = word.get(
                    "word",
                    ""
                ).strip()

                if not text:
                    continue

                words.append(
                    {
                        "text": text,
                        "start_time": float(
                            word["start"]
                        ),
                        "end_time": float(
                            word["end"]
                        ),
                    }
                )

        if not words:
            raise RuntimeError(
                "Whisper produced no word timestamps."
            )

        return words

    async def align_phrases(
        self,
        audio_path: str,
    ) -> list[dict]:

        words = await self.align(
            audio_path
        )

        phrases = []

        current_group = []

        for word in words:

            if current_group:

                previous_word = (
                    current_group[-1]
                )

                pause = (
                    word["start_time"]
                    - previous_word["end_time"]
                )

                group_full = (
                    len(current_group)
                    >= self.WORDS_PER_PHRASE
                )

                natural_pause = (
                    pause
                    >= self.PAUSE_THRESHOLD
                )

                if (
                    group_full
                    or natural_pause
                ):

                    phrases.append(
                        self._build_phrase(
                            current_group
                        )
                    )

                    current_group = []

            current_group.append(
                word
            )

        if current_group:

            phrases.append(
                self._build_phrase(
                    current_group
                )
            )

        return phrases

    @staticmethod
    def _build_phrase(
        words: list[dict],
    ) -> dict:

        if not words:
            raise ValueError(
                "Cannot build caption phrase from no words."
            )

        start_time = max(
            0.0,
            float(
                words[0]["start_time"]
            ),
        )

        end_time = float(
            words[-1]["end_time"]
        )

        # Whisper occasionally produces identical or
        # slightly reversed word boundaries. Downstream
        # subtitle rendering requires positive duration.
        if end_time <= start_time:
            end_time = start_time + 0.08

        return {
            "text": " ".join(
                word["text"]
                for word in words
            ),
            "start_time": start_time,
            "end_time": end_time,
        }

    def _transcribe(
        self,
        audio_path: str,
    ) -> dict:

        model = self._load_model()

        return model.transcribe(
            audio_path,
            language="en",
            word_timestamps=True,
            fp16=False,
        )
