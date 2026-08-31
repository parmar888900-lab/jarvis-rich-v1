
"""Microphone confirmation-listener regressions."""

import asyncio

from backend.services.voice.assistant import (
    VoiceAssistant,
)

from backend.services.voice.command_router import (
    VoiceCommand,
)

from backend.services.voice.confirmation import (
    VoiceConfirmationManager,
)


class FakeCommander:
    def __init__(self):
        self.calls = []

    async def route(
        self,
        *,
        agent,
        task,
        command_id,
        parameters,
    ):
        self.calls.append(
            {
                "agent": agent,
                "task": task,
                "command_id": command_id,
                "parameters": parameters,
            }
        )

        return {
            "status": "success",
        }


class FakeCapture:
    def __init__(
        self,
        *,
        status="success",
        fail=False,
        malformed=False,
    ):
        self.status = status
        self.fail = fail
        self.malformed = malformed
        self.calls = []

    def record(
        self,
        audio_path,
        *,
        duration_seconds,
        on_ready,
    ):
        self.calls.append(
            {
                "audio_path": str(
                    audio_path
                ),
                "duration_seconds": duration_seconds,
            }
        )

        if self.fail:
            raise RuntimeError(
                "microphone failed"
            )

        if self.malformed:
            return "invalid"

        return {
            "status": self.status,
            "reason": (
                None
                if self.status == "success"
                else "capture_failed"
            ),
        }


class FakeTranscriber:
    def __init__(
        self,
        text="Confirm.",
        *,
        status="success",
        fail=False,
        malformed=False,
    ):
        self.text = text
        self.status = status
        self.fail = fail
        self.malformed = malformed
        self.calls = []

    def transcribe(
        self,
        audio_path,
    ):
        self.calls.append(
            str(
                audio_path
            )
        )

        if self.fail:
            raise RuntimeError(
                "whisper failed"
            )

        if self.malformed:
            return "invalid"

        return {
            "status": self.status,
            "text": self.text,
        }


class UnusedWakeParser:
    def __init__(self):
        self.calls = 0

    def parse(
        self,
        transcript,
    ):
        self.calls += 1

        raise AssertionError(
            "Confirmation must not require "
            "wake phrase parsing."
        )


class UnusedRouter:
    def parse(
        self,
        command_text,
    ):
        raise AssertionError(
            "Confirmation must not be reparsed "
            "as a new voice command."
        )


class FakeFormatter:
    def format(
        self,
        result,
    ):
        return "test"


class FakeSpeaker:
    async def speak(
        self,
        text,
        *,
        filename="jarvis_response",
    ):
        return {
            "status": "success",
        }


def pending_upload():
    return VoiceCommand(
        status="ready",
        transcript="upload the video",
        agent="youtube",
        task="upload_video",
        parameters={
            "privacy_status": "private",
            "artifact": "test.mp4",
        },
        requires_confirmation=True,
    )


def build_assistant(
    *,
    capture=None,
    transcriber=None,
):
    commander = FakeCommander()

    capture = (
        capture
        if capture is not None
        else FakeCapture()
    )

    transcriber = (
        transcriber
        if transcriber is not None
        else FakeTranscriber()
    )

    wake = UnusedWakeParser()

    manager = VoiceConfirmationManager(
        timeout_seconds=15
    )

    assistant = VoiceAssistant(
        commander=commander,
        transcriber=transcriber,
        wake_parser=wake,
        router=UnusedRouter(),
        audio_capture=capture,
        response_formatter=FakeFormatter(),
        response_speaker=FakeSpeaker(),
        confirmation_manager=manager,
    )

    return (
        assistant,
        commander,
        capture,
        transcriber,
        wake,
        manager,
    )


async def test_confirm_from_microphone_executes():
    (
        assistant,
        commander,
        capture,
        transcriber,
        wake,
        manager,
    ) = build_assistant()

    assert (
        manager.request(
            pending_upload()
        ).status
        == "pending"
    )

    result = await assistant.listen_for_confirmation(
        "confirm.wav",
        duration_seconds=4.0,
    )

    assert result.status == "completed"
    assert result.agent == "youtube"
    assert result.task == "upload_video"

    assert len(
        commander.calls
    ) == 1

    assert (
        commander.calls[0]["parameters"]
        == {
            "privacy_status": "private",
            "artifact": "test.mp4",
        }
    )

    assert wake.calls == 0
    assert not manager.has_pending


async def test_cancel_from_microphone_never_executes():
    transcriber = FakeTranscriber(
        text="No."
    )

    (
        assistant,
        commander,
        capture,
        transcriber,
        wake,
        manager,
    ) = build_assistant(
        transcriber=transcriber
    )

    manager.request(
        pending_upload()
    )

    result = await assistant.listen_for_confirmation(
        "cancel.wav"
    )

    assert (
        result.status
        == "confirmation_cancelled"
    )

    assert commander.calls == []
    assert wake.calls == 0
    assert not manager.has_pending


async def test_publication_phrase_is_blocked():
    transcriber = FakeTranscriber(
        text="Confirm and make it public."
    )

    (
        assistant,
        commander,
        capture,
        transcriber,
        wake,
        manager,
    ) = build_assistant(
        transcriber=transcriber
    )

    manager.request(
        pending_upload()
    )

    result = await assistant.listen_for_confirmation(
        "public.wav"
    )

    assert result.status == "blocked"

    assert (
        result.reason
        == "public_release_not_available_by_voice"
    )

    assert commander.calls == []
    assert not manager.has_pending


async def test_unknown_phrase_fails_closed():
    transcriber = FakeTranscriber(
        text="Maybe later."
    )

    (
        assistant,
        commander,
        capture,
        transcriber,
        wake,
        manager,
    ) = build_assistant(
        transcriber=transcriber
    )

    manager.request(
        pending_upload()
    )

    result = await assistant.listen_for_confirmation(
        "unknown.wav"
    )

    assert (
        result.status
        == "confirmation_rejected"
    )

    assert commander.calls == []
    assert not manager.has_pending


async def test_no_pending_does_not_open_microphone():
    (
        assistant,
        commander,
        capture,
        transcriber,
        wake,
        manager,
    ) = build_assistant()

    result = await assistant.listen_for_confirmation(
        "unused.wav"
    )

    assert (
        result.status
        == "confirmation_not_pending"
    )

    assert capture.calls == []
    assert transcriber.calls == []
    assert commander.calls == []


async def test_capture_exception_clears_pending():
    capture = FakeCapture(
        fail=True
    )

    (
        assistant,
        commander,
        capture,
        transcriber,
        wake,
        manager,
    ) = build_assistant(
        capture=capture
    )

    manager.request(
        pending_upload()
    )

    result = await assistant.listen_for_confirmation(
        "capture.wav"
    )

    assert result.status == "capture_failed"
    assert commander.calls == []
    assert not manager.has_pending


async def test_malformed_capture_clears_pending():
    capture = FakeCapture(
        malformed=True
    )

    (
        assistant,
        commander,
        capture,
        transcriber,
        wake,
        manager,
    ) = build_assistant(
        capture=capture
    )

    manager.request(
        pending_upload()
    )

    result = await assistant.listen_for_confirmation(
        "capture.wav"
    )

    assert result.status == "capture_failed"
    assert commander.calls == []
    assert not manager.has_pending


async def test_transcription_failure_clears_pending():
    transcriber = FakeTranscriber(
        status="no_speech",
        text="",
    )

    (
        assistant,
        commander,
        capture,
        transcriber,
        wake,
        manager,
    ) = build_assistant(
        transcriber=transcriber
    )

    manager.request(
        pending_upload()
    )

    result = await assistant.listen_for_confirmation(
        "silent.wav"
    )

    assert result.status == "no_speech"
    assert commander.calls == []
    assert not manager.has_pending


async def test_transcription_exception_clears_pending():
    transcriber = FakeTranscriber(
        fail=True
    )

    (
        assistant,
        commander,
        capture,
        transcriber,
        wake,
        manager,
    ) = build_assistant(
        transcriber=transcriber
    )

    manager.request(
        pending_upload()
    )

    result = await assistant.listen_for_confirmation(
        "whisper.wav"
    )

    assert result.status == "no_speech"
    assert commander.calls == []
    assert not manager.has_pending


async def test_malformed_transcription_clears_pending():
    transcriber = FakeTranscriber(
        malformed=True
    )

    (
        assistant,
        commander,
        capture,
        transcriber,
        wake,
        manager,
    ) = build_assistant(
        transcriber=transcriber
    )

    manager.request(
        pending_upload()
    )

    result = await assistant.listen_for_confirmation(
        "whisper.wav"
    )

    assert result.status == "no_speech"
    assert commander.calls == []
    assert not manager.has_pending


async def test_confirmation_is_not_replayable():
    (
        assistant,
        commander,
        capture,
        transcriber,
        wake,
        manager,
    ) = build_assistant()

    manager.request(
        pending_upload()
    )

    first = await assistant.listen_for_confirmation(
        "first.wav"
    )

    second = await assistant.listen_for_confirmation(
        "second.wav"
    )

    assert first.status == "completed"

    assert (
        second.status
        == "confirmation_not_pending"
    )

    assert len(
        commander.calls
    ) == 1

    # Second call must not even reopen the microphone.
    assert len(
        capture.calls
    ) == 1


async def main():
    await test_confirm_from_microphone_executes()
    print(
        "PASS: microphone confirmation executes exact pending command."
    )

    await test_cancel_from_microphone_never_executes()
    print(
        "PASS: microphone cancellation executes nothing."
    )

    await test_publication_phrase_is_blocked()
    print(
        "PASS: microphone publication phrase remains blocked."
    )

    await test_unknown_phrase_fails_closed()
    print(
        "PASS: unknown microphone confirmation fails closed."
    )

    await test_no_pending_does_not_open_microphone()
    print(
        "PASS: microphone stays closed without pending confirmation."
    )

    await test_capture_exception_clears_pending()
    print(
        "PASS: confirmation capture exception clears authorization."
    )

    await test_malformed_capture_clears_pending()
    print(
        "PASS: malformed confirmation capture clears authorization."
    )

    await test_transcription_failure_clears_pending()
    print(
        "PASS: no-speech confirmation clears authorization."
    )

    await test_transcription_exception_clears_pending()
    print(
        "PASS: confirmation STT exception clears authorization."
    )

    await test_malformed_transcription_clears_pending()
    print(
        "PASS: malformed confirmation STT clears authorization."
    )

    await test_confirmation_is_not_replayable()
    print(
        "PASS: microphone confirmation remains single-use."
    )

    print()
    print(
        "PASS: microphone confirmation listener "
        "regression suite complete."
    )


if __name__ == "__main__":
    asyncio.run(
        main()
    )
