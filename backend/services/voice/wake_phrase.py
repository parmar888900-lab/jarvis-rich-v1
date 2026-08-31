"""Deterministic wake-phrase parsing for Jarvis voice input."""

from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class WakePhraseMatch:
    """Result of checking recognized speech for the wake phrase."""

    detected: bool
    command: str
    transcript: str


class WakePhraseParser:
    """Extract commands that explicitly address Jarvis."""

    DEFAULT_WAKE_PHRASE = "hey jarvis"

    def __init__(
        self,
        wake_phrase: str = DEFAULT_WAKE_PHRASE,
    ) -> None:
        clean_phrase = self._normalize_text(
            wake_phrase
        )

        if not clean_phrase:
            raise ValueError(
                "Wake phrase cannot be empty."
            )

        self.wake_phrase = clean_phrase

        words = [
            re.escape(word)
            for word in clean_phrase.split()
        ]

        # Require the wake phrase at the beginning of the
        # recognized utterance. This prevents ordinary speech
        # containing "hey Jarvis" later in a sentence from
        # accidentally becoming a command.
        self._pattern = re.compile(
            r"^\s*"
            + r"[\s,.:;!?-]*".join(words)
            + r"(?:\s*[,.:;!?-]\s*|\s+|$)",
            flags=re.IGNORECASE,
        )

    def parse(
        self,
        transcript: str,
    ) -> WakePhraseMatch:
        """Parse one speech-recognition transcript."""

        raw = str(transcript or "").strip()

        if not raw:
            return WakePhraseMatch(
                detected=False,
                command="",
                transcript="",
            )

        match = self._pattern.match(raw)

        if match is None:
            return WakePhraseMatch(
                detected=False,
                command="",
                transcript=raw,
            )

        command = raw[match.end():].strip()

        command = re.sub(
            r"^[\s,.:;!?-]+",
            "",
            command,
        ).strip()

        return WakePhraseMatch(
            detected=True,
            command=command,
            transcript=raw,
        )

    def is_wake_only(
        self,
        transcript: str,
    ) -> bool:
        """Return True when speech contains only the wake phrase."""

        result = self.parse(transcript)

        return (
            result.detected
            and not result.command
        )

    @staticmethod
    def _normalize_text(
        value: str,
    ) -> str:
        text = str(value or "").strip().lower()

        text = re.sub(
            r"\s+",
            " ",
            text,
        )

        return text
