"""Regression tests for Jarvis Whisper transcription."""

from pathlib import Path
from tempfile import TemporaryDirectory

from backend.services.voice.transcriber import (
    WhisperTranscriber,
)


class FakeWhisperModel:
    def __init__(
        self,
        result,
    ):
        self.result = result
        self.calls = []

    def transcribe(
        self,
        audio_path,
        **kwargs,
    ):
        self.calls.append(
            {
                "audio_path": audio_path,
                "kwargs": kwargs,
            }
        )

        return self.result


def make_audio_file(
    directory: str,
) -> Path:
    path = Path(directory) / "voice-test.wav"

    # Unit tests do not decode this file because the Whisper
    # model is replaced with a deterministic fake.
    path.write_bytes(b"test-audio")

    return path


def main():
    with TemporaryDirectory() as directory:
        audio_path = make_audio_file(
            directory
        )

        fake = FakeWhisperModel(
            {
                "text": (
                    "  Hey Jarvis, analyze today's trends  "
                ),
                "language": "en",
            }
        )

        transcriber = WhisperTranscriber(
            model_name="tiny.en",
            model=fake,
        )

        result = transcriber.transcribe(
            audio_path
        )

        assert result["status"] == "success"

        assert (
            result["text"]
            == "Hey Jarvis, analyze today's trends"
        )

        assert result["model"] == "tiny.en"
        assert result["language"] == "en"

        assert len(fake.calls) == 1

        call = fake.calls[0]

        assert (
            call["audio_path"]
            == str(audio_path)
        )

        assert call["kwargs"]["fp16"] is False
        assert call["kwargs"]["language"] == "en"

        assert (
            call["kwargs"]["task"]
            == "transcribe"
        )

        print(
            "PASS: recognized speech is normalized."
        )


        silent_fake = FakeWhisperModel(
            {
                "text": "   ",
                "language": "en",
            }
        )

        silent = WhisperTranscriber(
            model=silent_fake
        )

        result = silent.transcribe(
            audio_path
        )

        assert result["status"] == "no_speech"
        assert result["text"] == ""

        print(
            "PASS: empty recognition becomes no_speech."
        )


        malformed_fake = FakeWhisperModel(
            "invalid"
        )

        malformed = WhisperTranscriber(
            model=malformed_fake
        )

        try:
            malformed.transcribe(
                audio_path
            )
        except RuntimeError:
            pass
        else:
            raise AssertionError(
                "Malformed Whisper result must fail."
            )

        print(
            "PASS: malformed Whisper output fails closed."
        )


        missing = WhisperTranscriber(
            model=fake
        )

        try:
            missing.transcribe(
                Path(directory) / "missing.wav"
            )
        except FileNotFoundError:
            pass
        else:
            raise AssertionError(
                "Missing audio must fail."
            )

        print(
            "PASS: missing audio fails before Whisper."
        )


        try:
            WhisperTranscriber(
                model_name="   ",
                model=fake,
            )
        except ValueError:
            pass
        else:
            raise AssertionError(
                "Empty model name must fail."
            )

        print(
            "PASS: empty model configuration fails closed."
        )

    print()
    print(
        "PASS: Whisper transcriber regression suite complete."
    )


if __name__ == "__main__":
    main()
