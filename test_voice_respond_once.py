
"""Regression tests for VoiceAssistant.respond_once()."""

import asyncio

from backend.services.voice.assistant import (
    VoiceAssistant,
    VoiceAssistantResult,
)


class FakeFormatter:
    def __init__(
        self,
        text="Response text.",
        *,
        fail=False,
    ):
        self.text = text
        self.fail = fail
        self.calls = []

    def format(
        self,
        result,
    ):
        self.calls.append(
            result
        )

        if self.fail:
            raise RuntimeError(
                "formatter failed"
            )

        return self.text


class FakeSpeaker:
    def __init__(
        self,
        *,
        result=None,
        fail=False,
    ):
        self.result = (
            result
            if result is not None
            else {
                "status": "success",
                "audio_path": "fake.wav",
            }
        )

        self.fail = fail
        self.calls = []

    async def speak(
        self,
        text,
        *,
        filename="jarvis_response",
    ):
        self.calls.append(
            {
                "text": text,
                "filename": filename,
            }
        )

        if self.fail:
            raise RuntimeError(
                "speaker failed"
            )

        return self.result


class FakeCapture:
    def record(
        self,
        audio_path,
        *,
        duration_seconds,
        on_ready,
    ):
        return {
            "status": "success",
            "audio_path": str(
                audio_path
            ),
        }


class FakeTranscriber:
    def __init__(
        self,
        text=(
            "Hey Jarvis, "
            "analyze today's trends."
        ),
    ):
        self.text = text

    def transcribe(
        self,
        audio_path,
    ):
        return {
            "status": "success",
            "text": self.text,
        }


class FakeWake:
    def parse(
        self,
        transcript,
    ):
        class Result:
            detected = True
            command = (
                "analyze today's trends."
            )

        return Result()


class FakeRouter:
    def parse(
        self,
        command_text,
    ):
        class Command:
            status = "ready"
            agent = "youtube"
            task = "analyze_trends"
            parameters = {}
            requires_confirmation = False
            reason = None

        return Command()


class FakeExecution:
    status = "completed"
    command_id = "voice-test"
    agent = "youtube"
    task = "analyze_trends"
    reason = None

    result = {
        "status": "success",
        "final_trend_count": 10,
        "best_trend": {
            "title": "Test Trend",
        },
    }


class FakeExecutor:
    async def execute(
        self,
        command,
        *,
        confirmed=False,
    ):
        return FakeExecution()


def build_assistant(
    *,
    formatter=None,
    speaker=None,
):
    return VoiceAssistant(
        commander=object(),
        transcriber=FakeTranscriber(),
        wake_parser=FakeWake(),
        router=FakeRouter(),
        executor=FakeExecutor(),
        audio_capture=FakeCapture(),
        response_formatter=(
            formatter
            if formatter is not None
            else FakeFormatter()
        ),
        response_speaker=(
            speaker
            if speaker is not None
            else FakeSpeaker()
        ),
    )


async def test_successful_response():
    formatter = FakeFormatter(
        "Trend analysis complete."
    )

    speaker = FakeSpeaker()

    assistant = build_assistant(
        formatter=formatter,
        speaker=speaker,
    )

    result = await assistant.respond_once(
        "fake.wav",
        duration_seconds=8.0,
        response_filename="respond_once_test",
    )

    assert result.status == "completed"
    assert (
        result.assistant_result.status
        == "completed"
    )

    assert (
        result.response_text
        == "Trend analysis complete."
    )

    assert (
        result.speech_status
        == "success"
    )

    assert result.speech is not None

    assert len(
        speaker.calls
    ) == 1

    assert (
        speaker.calls[0]["filename"]
        == "respond_once_test"
    )


async def test_speaker_exception_preserves_command():
    speaker = FakeSpeaker(
        fail=True
    )

    assistant = build_assistant(
        speaker=speaker,
    )

    result = await assistant.respond_once(
        "fake.wav"
    )

    # Critical invariant:
    # speaker failure MUST NOT corrupt
    # successful command execution.
    assert result.status == "completed"

    assert (
        result.assistant_result.status
        == "completed"
    )

    assert (
        result.response_text
        == "Response text."
    )

    assert (
        result.speech_status
        == "failed"
    )

    assert (
        result.speech_reason
        == "speech_exception:RuntimeError"
    )


async def test_invalid_speaker_result_preserves_command():
    speaker = FakeSpeaker(
        result="invalid"
    )

    assistant = build_assistant(
        speaker=speaker,
    )

    result = await assistant.respond_once(
        "fake.wav"
    )

    assert result.status == "completed"

    assert (
        result.response_text
        == "Response text."
    )

    assert (
        result.speech_status
        == "failed"
    )

    assert (
        result.speech_reason
        == "invalid_speech_result"
    )


async def test_unsuccessful_speaker_result_preserves_command():
    speaker = FakeSpeaker(
        result={
            "status": "failed",
            "reason": "output_device_failed",
        }
    )

    assistant = build_assistant(
        speaker=speaker,
    )

    result = await assistant.respond_once(
        "fake.wav"
    )

    assert result.status == "completed"

    assert (
        result.response_text
        == "Response text."
    )

    assert (
        result.speech_status
        == "failed"
    )

    assert (
        result.speech_reason
        == "output_device_failed"
    )


async def test_empty_response_does_not_call_speaker():
    speaker = FakeSpeaker()

    assistant = build_assistant(
        formatter=FakeFormatter(
            ""
        ),
        speaker=speaker,
    )

    result = await assistant.respond_once(
        "fake.wav"
    )

    assert result.status == "completed"

    assert result.response_text == ""

    assert (
        result.speech_status
        == "silent"
    )

    assert (
        result.speech_reason
        == "empty_response"
    )

    assert speaker.calls == []


async def test_formatter_failure_preserves_command():
    assistant = build_assistant(
        formatter=FakeFormatter(
            fail=True
        ),
    )

    result = await assistant.respond_once(
        "fake.wav"
    )

    assert result.status == "completed"

    assert result.response_text == ""

    assert (
        result.speech_status
        == "not_attempted"
    )

    assert (
        result.speech_reason
        == "response_format_exception:RuntimeError"
    )


async def main():
    await test_successful_response()

    await test_speaker_exception_preserves_command()

    await test_invalid_speaker_result_preserves_command()

    await test_unsuccessful_speaker_result_preserves_command()

    await test_empty_response_does_not_call_speaker()

    await test_formatter_failure_preserves_command()

    print(
        "PASS: VoiceAssistant.respond_once "
        "regressions passed."
    )


if __name__ == "__main__":
    asyncio.run(
        main()
    )
