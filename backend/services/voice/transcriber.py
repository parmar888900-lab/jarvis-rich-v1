"""Local speech-to-text for the Jarvis voice assistant."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import whisper


class WhisperTranscriber:
    """Transcribe local audio with OpenAI Whisper."""

    def __init__(
        self,
        model_name: str = "tiny.en",
        *,
        model: Any | None = None,
    ) -> None:
        clean_model_name = str(
            model_name or ""
        ).strip()

        if not clean_model_name:
            raise ValueError(
                "Whisper model name cannot be empty."
            )

        self.model_name = clean_model_name
        self._model = model

    def _get_model(self):
        """Load Whisper lazily so startup stays lightweight."""

        if self._model is None:
            self._model = whisper.load_model(
                self.model_name
            )

        return self._model

    def transcribe(
        self,
        audio_path: str | Path,
    ) -> dict:
        """Transcribe one audio file."""

        path = Path(audio_path)

        if not path.exists():
            raise FileNotFoundError(
                f"Audio file not found: {path}"
            )

        if not path.is_file():
            raise ValueError(
                f"Audio path is not a file: {path}"
            )

        model = self._get_model()

        result = model.transcribe(
            str(path),
            fp16=False,
            language="en",
            task="transcribe",
        )

        if not isinstance(result, dict):
            raise RuntimeError(
                "Whisper returned an invalid result."
            )

        text = str(
            result.get("text") or ""
        ).strip()

        return {
            "status": (
                "success"
                if text
                else "no_speech"
            ),
            "text": text,
            "audio_path": str(path),
            "model": self.model_name,
            "language": str(
                result.get("language")
                or "en"
            ),
        }
