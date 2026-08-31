
"""VoiceAssistant confirmation integration regressions."""

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


class FakeTranscriber:
    def __init__(self):
        self.text = (
            "Hey Jarvis, upload the video."
        )

    def transcribe(
        self,
        audio_path,
    ):
        return {
            "status": "success",
            "text": self.text,
        }


class FakeWakeResult:
    detected = True
    command = "upload the video."


class FakeWakeParser:
    def parse(
        self,
        transcript,
    ):
        return FakeWakeResult()


class FakeRouter:
    def __init__(self):
        self.command = VoiceCommand(
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

    def parse(
        self,
        command_text,
    ):
        return self.command


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
        }


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
            "text": text,
        }


def build_assistant():
    commander = FakeCommander()

    router = FakeRouter()

    manager = VoiceConfirmationManager(
        timeout_seconds=15
    )

    assistant = VoiceAssistant(
        commander=commander,
        transcriber=FakeTranscriber(),
        wake_parser=FakeWakeParser(),
        router=router,
        audio_capture=FakeCapture(),
        response_formatter=FakeFormatter(),
        response_speaker=FakeSpeaker(),
        confirmation_manager=manager,
    )

    return (
        assistant,
        commander,
        router,
        manager,
    )


async def test_pending_command_is_not_executed():
    (
        assistant,
        commander,
        router,
        manager,
    ) = build_assistant()

    result = await assistant.process_audio(
        "fake.wav"
    )

    assert (
        result.status
        == "confirmation_required"
    )

    assert result.agent == "youtube"
    assert result.task == "upload_video"

    assert commander.calls == []

    assert manager.has_pending


async def test_confirm_executes_exact_pending_command():
    (
        assistant,
        commander,
        router,
        manager,
    ) = build_assistant()

    await assistant.process_audio(
        "fake.wav"
    )

    result = await assistant.resolve_confirmation(
        "Confirm."
    )

    assert result.status == "completed"

    assert result.agent == "youtube"
    assert result.task == "upload_video"

    assert len(
        commander.calls
    ) == 1

    call = commander.calls[0]

    assert (
        call["parameters"]
        == {
            "privacy_status": "private",
            "artifact": "test.mp4",
        }
    )

    assert not manager.has_pending


async def test_confirmation_is_single_use():
    (
        assistant,
        commander,
        router,
        manager,
    ) = build_assistant()

    await assistant.process_audio(
        "fake.wav"
    )

    first = await assistant.resolve_confirmation(
        "confirm"
    )

    second = await assistant.resolve_confirmation(
        "confirm"
    )

    assert first.status == "completed"

    assert (
        second.status
        == "confirmation_not_pending"
    )

    assert len(
        commander.calls
    ) == 1


async def test_cancel_never_executes():
    (
        assistant,
        commander,
        router,
        manager,
    ) = build_assistant()

    await assistant.process_audio(
        "fake.wav"
    )

    result = await assistant.resolve_confirmation(
        "No"
    )

    assert (
        result.status
        == "confirmation_cancelled"
    )

    assert commander.calls == []
    assert not manager.has_pending


async def test_unknown_confirmation_never_executes():
    (
        assistant,
        commander,
        router,
        manager,
    ) = build_assistant()

    await assistant.process_audio(
        "fake.wav"
    )

    result = await assistant.resolve_confirmation(
        "maybe"
    )

    assert (
        result.status
        == "confirmation_rejected"
    )

    assert commander.calls == []
    assert not manager.has_pending


async def test_publication_language_never_executes():
    (
        assistant,
        commander,
        router,
        manager,
    ) = build_assistant()

    await assistant.process_audio(
        "fake.wav"
    )

    result = await assistant.resolve_confirmation(
        "confirm and make it public"
    )

    assert result.status == "blocked"

    assert (
        result.reason
        == "public_release_not_available_by_voice"
    )

    assert commander.calls == []
    assert not manager.has_pending


async def test_confirm_does_not_reparse_new_command():
    (
        assistant,
        commander,
        router,
        manager,
    ) = build_assistant()

    original = router.command

    await assistant.process_audio(
        "fake.wav"
    )

    # Change what the router would return AFTER the
    # original command became pending.
    router.command = VoiceCommand(
        status="ready",
        transcript="analyze today's trends",
        agent="youtube",
        task="analyze_trends",
        parameters={
            "forged": True,
        },
        requires_confirmation=False,
    )

    result = await assistant.resolve_confirmation(
        "confirm"
    )

    assert result.status == "completed"

    assert len(
        commander.calls
    ) == 1

    call = commander.calls[0]

    # Confirmation executes the stored command,
    # not the router's new command.
    assert call["task"] == "upload_video"

    assert (
        call["parameters"]
        == original.parameters
    )


async def test_forged_publish_pending_is_blocked():
    (
        assistant,
        commander,
        router,
        manager,
    ) = build_assistant()

    forged = VoiceCommand(
        status="ready",
        transcript="publish video",
        agent="youtube",
        task="publish_video",
        parameters={},
        requires_confirmation=True,
    )

    pending = manager.request(
        forged
    )

    assert pending.status == "blocked"

    result = await assistant.resolve_confirmation(
        "confirm"
    )

    assert (
        result.status
        == "confirmation_not_pending"
    )

    assert commander.calls == []


async def main():
    await test_pending_command_is_not_executed()
    print(
        "PASS: sensitive command becomes pending without execution."
    )

    await test_confirm_executes_exact_pending_command()
    print(
        "PASS: confirmation executes exact stored command."
    )

    await test_confirmation_is_single_use()
    print(
        "PASS: confirmed command cannot be replayed."
    )

    await test_cancel_never_executes()
    print(
        "PASS: cancellation never reaches Commander."
    )

    await test_unknown_confirmation_never_executes()
    print(
        "PASS: unknown confirmation fails closed."
    )

    await test_publication_language_never_executes()
    print(
        "PASS: publication language cannot ride confirmation."
    )

    await test_confirm_does_not_reparse_new_command()
    print(
        "PASS: confirmation does not reparse a new command."
    )

    await test_forged_publish_pending_is_blocked()
    print(
        "PASS: forged publication cannot enter confirmation state."
    )

    print()
    print(
        "PASS: VoiceAssistant confirmation "
        "integration regressions complete."
    )


if __name__ == "__main__":
    asyncio.run(
        main()
    )
