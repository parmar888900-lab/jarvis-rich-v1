"""
Speech-aligned caption timing using OpenAI Whisper.
"""

import asyncio
import math
import re
from pathlib import Path

import whisper


class CaptionAlignmentError(RuntimeError):
    """The transcript cannot safely provide timings for the supplied script."""


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

        return self._group_phrases(words)

    async def align_script_phrases(
        self,
        audio_path: str,
        script_text: str,
    ) -> list[dict]:
        """Use Whisper for timing and the spoken, grounded script for wording.

        Recognition mistakes must never become newly authored caption claims.
        Only small, locally bounded transcript errors are repaired; an unrelated
        or badly truncated transcript raises instead of inventing uniform timing.
        """
        observed = await self.align(audio_path)
        return self._group_phrases(self.align_script_words(script_text, observed))

    def _group_phrases(self, words: list[dict]) -> list[dict]:

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

    @classmethod
    def align_script_words(cls, script_text: str, observed: list[dict]) -> list[dict]:
        """Align original script words to an already timed ASR transcript.

        This pure helper also supports safe reuse of a cached transcription.
        Returned text is exclusively from ``script_text``. Missing words receive
        local timing bounded by their neighbours, never whole-track estimation.
        """
        source_words = script_text.split()
        if not source_words or not observed:
            raise CaptionAlignmentError("Script and timed transcript are required.")
        source = [(token, i) for i, word in enumerate(source_words)
                  for token in cls._alignment_tokens(word)]
        target = []
        previous_end = 0.0
        for word in observed:
            start, end = float(word["start_time"]), float(word["end_time"])
            if (not math.isfinite(start) or not math.isfinite(end)
                    or start < 0 or end <= start or start < previous_end - 0.04):
                raise CaptionAlignmentError("Transcript has invalid word timestamps.")
            start = max(start, previous_end)
            tokens = cls._alignment_tokens(word["text"])
            if end <= start:
                raise CaptionAlignmentError("Transcript has overlapping word timestamps.")
            for i, token in enumerate(tokens):
                target.append((token, start + (end - start) * i / len(tokens),
                               start + (end - start) * (i + 1) / len(tokens)))
            previous_end = end
        if not source or not target:
            raise CaptionAlignmentError("Script or transcript has no alignable words.")

        # Levenshtein alignment retains ordering and handles substitutions,
        # inserted ASR words and dropped ASR words without copying their text.
        n, m = len(source), len(target)
        costs = [list(range(m + 1))] + [[i] + [0] * m for i in range(1, n + 1)]
        for i in range(1, n + 1):
            for j in range(1, m + 1):
                costs[i][j] = min(costs[i - 1][j] + 1, costs[i][j - 1] + 1,
                                  costs[i - 1][j - 1] + (source[i - 1][0] != target[j - 1][0]))
        pairs, anchors = {}, []
        i, j = n, m
        while i or j:
            equal = bool(i and j and source[i - 1][0] == target[j - 1][0])
            if i and j and costs[i][j] == costs[i - 1][j - 1] + (not equal):
                pairs[i - 1] = j - 1
                if equal:
                    anchors.append((i - 1, j - 1))
                i, j = i - 1, j - 1
            elif i and costs[i][j] == costs[i - 1][j] + 1:
                i -= 1
            else:
                j -= 1
        anchors.reverse()
        if len(anchors) / max(n, m) < 0.65:
            raise CaptionAlignmentError("Script/transcript agreement is too low for caption timing.")
        boundaries = [(-1, -1), *anchors, (n, m)]
        for (si, ti), (sj, tj) in zip(boundaries, boundaries[1:]):
            if sj - si - 1 > 8 or tj - ti - 1 > 10:
                raise CaptionAlignmentError("Unmatched transcript passage is too long to time safely.")
            if sj - si > 1 or tj - ti > 1:
                start = target[ti][2] if ti >= 0 else target[0][1]
                end = target[tj][1] if tj < m else target[-1][2]
                if end - start > 3.5:
                    raise CaptionAlignmentError("Unmatched caption passage exceeds its timing budget.")

        windows = [None] * len(source_words)
        for source_index, target_index in pairs.items():
            owner = source[source_index][1]
            _, start, end = target[target_index]
            existing = windows[owner]
            windows[owner] = (min(existing[0], start), max(existing[1], end)) if existing else (start, end)

        # Interpolate only missing local words. When ASR attached their speech to
        # neighbouring tokens, borrow that small neighbouring window explicitly.
        index = 0
        while index < len(windows):
            if windows[index] is not None:
                index += 1
                continue
            first = index
            while index < len(windows) and windows[index] is None:
                index += 1
            last = index
            start = windows[first - 1][1] if first else target[0][1]
            end = windows[last][0] if last < len(windows) else target[-1][2]
            if end - start < 0.04 * (last - first):
                if first:
                    first -= 1
                    start = windows[first][0]
                if last < len(windows):
                    end = windows[last][1]
                    last += 1
            if end <= start or end - start > 3.5:
                raise CaptionAlignmentError("Missing script words have no reliable local timing window.")
            width = (end - start) / (last - first)
            for k in range(first, last):
                windows[k] = (start + width * (k - first), start + width * (k - first + 1))

        result = []
        previous_end = 0.0
        for text, window in zip(source_words, windows):
            start, end = window
            start = max(start, previous_end)
            if end <= start:
                raise CaptionAlignmentError("Aligned script words have invalid timing order.")
            result.append({"text": text, "start_time": start, "end_time": end})
            previous_end = end
        return result

    @classmethod
    def _alignment_tokens(cls, text: str) -> list[str]:
        text = text.lower().replace("’", "'")
        text = re.sub(r"\bm[²2]\b", "square meters", text)
        text = re.sub(r"\bsq\.?\b", "square", text)
        text = re.sub(r"\bft\b", "feet", text)
        text = re.sub(r"\bmetres?\b", "meters", text)
        contractions = {"can't": "can not", "won't": "will not", "it's": "it is",
                        "that's": "that is", "there's": "there is", "we're": "we are",
                        "they're": "they are", "isn't": "is not", "don't": "do not"}
        for short, expanded in contractions.items():
            text = re.sub(r"\b" + re.escape(short) + r"\b", expanded, text)
        parts = re.findall(r"[a-z]+|\d+", text)
        return [token for part in parts for token in
                (cls._number_tokens(int(part)) if part.isdigit() else [part])]

    @classmethod
    def _number_tokens(cls, number: int) -> list[str]:
        units = "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split()
        tens = "zero ten twenty thirty forty fifty sixty seventy eighty ninety".split()
        if number < 20:
            return [units[number]]
        if number < 100:
            return [tens[number // 10]] + (cls._number_tokens(number % 10) if number % 10 else [])
        for magnitude, name in ((1_000_000, "million"), (1_000, "thousand"), (100, "hundred")):
            if number >= magnitude:
                return (cls._number_tokens(number // magnitude) + [name]
                        + (cls._number_tokens(number % magnitude) if number % magnitude else []))
        return [str(number)]

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
