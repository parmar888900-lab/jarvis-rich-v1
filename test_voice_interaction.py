
"""Complete two-turn VoiceAssistant interaction regressions."""

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


class SequenceCapture:
    def __init__(self):
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
                "path": str(audio_path),
                "duration": duration_seconds,
            }
        )

        if on_ready is not None:
            on_ready()

        return {
            "status": "success",
        }


class SequenceTranscriber:
    def __init__(
        self,
        texts,
    ):
        self.texts = list(
            texts
        )

        self.calls = []

    def transcribe(
        self,
        audio_path,
    ):
        self.calls.append(
            str(audio_path)
        )

        if not self.texts:
            raise AssertionError(
                "Unexpected transcription call."
            )

        text = self.texts.pop(0)

        return {
            "status": "success",
            "text": text,
        }


class FakeWake:
    def __init__(
        self,
        detected,
        command,
    ):
        self.detected = detected
        self.command = command


class FakeWakeParser:
    def __init__(self):
        self.calls = []

    def parse(
        self,
        transcript,
    ):
        self.calls.append(
            transcript
        )

        lowered = transcript.lower()

        if lowered.startswith(
            "hey jarvis"
        ):
            command = transcript[
                len("hey jarvis"):
            ].strip(
                " ,.!?"
            )

            return FakeWake(
                True,
                command,
            )

        return FakeWake(
            False,
            "",
        )


class FakeRouter:
    def __init__(
        self,
        *,
        confirmation_required=True,
    ):
        self.confirmation_required = (
            confirmation_required
        )

        self.calls = []

    def parse(
        self,
        command_text,
    ):
        self.calls.append(
            command_text
        )

        if self.confirmation_required:
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

        return VoiceCommand(
            status="ready",
            transcript="analyze today's trends",
            agent="youtube",
            task="analyze_trends",
            parameters={},
            requires_confirmation=False,
        )


class FakeFormatter:
    def __init__(self):
        self.calls = []

    def format(
        self,
        result,
    ):
        self.calls.append(
            result.status
        )

        messages = {
            "confirmation_required":
                "This action requires confirmation.",
            "completed":
                "Done.",
            "confirmation_cancelled":
                "Cancelled.",
            "confirmation_rejected":
                "I did not receive a valid confirmation.",
            "blocked":
                "That action is not available by voice.",
            "no_speech":
                "I did not hear a confirmation.",
            "capture_failed":
                "I could not capture the confirmation.",
        }

        return messages.get(
            result.status,
            "Request failed.",
        )


class FakeSpeaker:
    def __init__(
        self,
        *,
        fail_on_call=None,
    ):
        self.calls = []
        self.fail_on_call = fail_on_call

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

        if (
            self.fail_on_call is not None
            and len(self.calls)
            == self.fail_on_call
        ):
            raise RuntimeError(
                "speaker failed"
            )

        return {
            "status": "success",
        }


def build_assistant(
    texts,
    *,
    confirmation_required=True,
    speaker=None,
):
    commander = FakeCommander()
    capture = SequenceCapture()
    transcriber = SequenceTranscriber(
        texts
    )
    wake = FakeWakeParser()

    router = FakeRouter(
        confirmation_required=(
            confirmation_required
        )
    )

    formatter = FakeFormatter()

    speaker = (
        speaker
        if speaker is not None
        else FakeSpeaker()
    )

    manager = VoiceConfirmationManager(
        timeout_seconds=15
    )

    assistant = VoiceAssistant(
        commander=commander,
        transcriber=transcriber,
        wake_parser=wake,
        router=router,
        audio_capture=capture,
        response_formatter=formatter,
        response_speaker=speaker,
        confirmation_manager=manager,
    )

    return {
        "assistant": assistant,
        "commander": commander,
        "capture": capture,
        "transcriber": transcriber,
        "wake": wake,
        "router": router,
        "formatter": formatter,
        "speaker": speaker,
        "manager": manager,
    }


async def test_complete_confirmed_interaction():
    ctx = build_assistant(
        [
            "Hey Jarvis, upload the video.",
            "Confirm.",
        ]
    )

    result = await ctx[
        "assistant"
    ].interact_once(
        "command.wav",
        confirmation_audio_path=(
            "confirmation.wav"
        ),
    )

    assert result.status == "completed"
    assert result.response_text == "Done."
    assert result.speech_status == "success"

    assert len(
        ctx["commander"].calls
    ) == 1

    call = ctx[
        "commander"
    ].calls[0]

    assert call["task"] == "upload_video"

    assert (
        call["parameters"]
        == {
            "privacy_status": "private",
            "artifact": "test.mp4",
        }
    )

    # One capture for command, one for confirmation.
    assert len(
        ctx["capture"].calls
    ) == 2

    # Wake phrase only applies to first utterance.
    assert len(
        ctx["wake"].calls
    ) == 1

    # Router only parses first utterance.
    assert len(
        ctx["router"].calls
    ) == 1

    # Prompt + final response.
    assert len(
        ctx["speaker"].calls
    ) == 2

    assert not ctx[
        "manager"
    ].has_pending


async def test_cancelled_interaction():
    ctx = build_assistant(
        [
            "Hey Jarvis, upload the video.",
            "No.",
        ]
    )

    result = await ctx[
        "assistant"
    ].interact_once(
        "command.wav",
        confirmation_audio_path=(
            "confirmation.wav"
        ),
    )

    assert (
        result.status
        == "confirmation_cancelled"
    )

    assert ctx[
        "commander"
    ].calls == []

    assert len(
        ctx["speaker"].calls
    ) == 2

    assert not ctx[
        "manager"
    ].has_pending


async def test_publication_rider_is_blocked():
    ctx = build_assistant(
        [
            "Hey Jarvis, upload the video.",
            "Confirm and make it public.",
        ]
    )

    result = await ctx[
        "assistant"
    ].interact_once(
        "command.wav",
        confirmation_audio_path=(
            "confirmation.wav"
        ),
    )

    assert result.status == "blocked"

    assert (
        result.assistant_result.reason
        == "public_release_not_available_by_voice"
    )

    assert ctx[
        "commander"
    ].calls == []

    assert not ctx[
        "manager"
    ].has_pending


async def test_safe_command_stays_single_turn():
    ctx = build_assistant(
        [
            "Hey Jarvis, analyze today's trends.",
        ],
        confirmation_required=False,
    )

    result = await ctx[
        "assistant"
    ].interact_once(
        "command.wav",
        confirmation_audio_path=(
            "should-not-be-used.wav"
        ),
    )

    assert result.status == "completed"

    assert len(
        ctx["capture"].calls
    ) == 1

    assert len(
        ctx["transcriber"].calls
    ) == 1

    assert len(
        ctx["commander"].calls
    ) == 1

    assert (
        ctx["commander"]
        .calls[0]["task"]
        == "analyze_trends"
    )

    assert len(
        ctx["speaker"].calls
    ) == 1


async def test_missing_confirmation_path_fails_closed():
    ctx = build_assistant(
        [
            "Hey Jarvis, upload the video.",
        ]
    )

    result = await ctx[
        "assistant"
    ].interact_once(
        "command.wav",
        confirmation_audio_path=None,
    )

    assert (
        result.status
        == "confirmation_cancelled"
    )

    assert (
        result.assistant_result.reason
        == "confirmation_audio_path_required"
    )

    assert ctx[
        "commander"
    ].calls == []

    assert not ctx[
        "manager"
    ].has_pending


async def test_final_speaker_failure_preserves_execution():
    speaker = FakeSpeaker(
        fail_on_call=2
    )

    ctx = build_assistant(
        [
            "Hey Jarvis, upload the video.",
            "Confirm.",
        ],
        speaker=speaker,
    )

    result = await ctx[
        "assistant"
    ].interact_once(
        "command.wav",
        confirmation_audio_path=(
            "confirmation.wav"
        ),
    )

    # Command remains completed.
    assert result.status == "completed"

    # Text fallback remains available.
    assert result.response_text == "Done."

    # Speech failure is independent.
    assert result.speech_status == "failed"

    assert (
        result.speech_reason
        == "speech_exception:RuntimeError"
    )

    assert len(
        ctx["commander"].calls
    ) == 1


async def test_prompt_speaker_failure_does_not_auto_confirm():
    speaker = FakeSpeaker(
        fail_on_call=1
    )

    ctx = build_assistant(
        [
            "Hey Jarvis, upload the video.",
            "Confirm.",
        ],
        speaker=speaker,
    )

    result = await ctx[
        "assistant"
    ].interact_once(
        "command.wav",
        confirmation_audio_path=(
            "confirmation.wav"
        ),
    )

    # Even if the spoken prompt failed, confirmation
    # still requires the explicit second utterance.
    assert result.status == "completed"

    assert len(
        ctx["commander"].calls
    ) == 1

    assert len(
        ctx["capture"].calls
    ) == 2


async def test_confirmation_cannot_be_reused_after_interaction():
    ctx = build_assistant(
        [
            "Hey Jarvis, upload the video.",
            "Confirm.",
        ]
    )

    result = await ctx[
        "assistant"
    ].interact_once(
        "command.wav",
        confirmation_audio_path=(
            "confirmation.wav"
        ),
    )

    assert result.status == "completed"

    replay = await ctx[
        "assistant"
    ].resolve_confirmation(
        "confirm"
    )

    assert (
        replay.status
        == "confirmation_not_pending"
    )

    assert len(
        ctx["commander"].calls
    ) == 1


async def main():
    await test_complete_confirmed_interaction()
    print(
        "PASS: complete two-turn confirmation executes once."
    )

    await test_cancelled_interaction()
    print(
        "PASS: complete two-turn cancellation executes nothing."
    )

    await test_publication_rider_is_blocked()
    print(
        "PASS: public-release rider remains blocked."
    )

    await test_safe_command_stays_single_turn()
    print(
        "PASS: safe command remains a one-turn interaction."
    )

    await test_missing_confirmation_path_fails_closed()
    print(
        "PASS: missing confirmation recording fails closed."
    )

    await test_final_speaker_failure_preserves_execution()
    print(
        "PASS: final speech failure preserves command completion."
    )

    await test_prompt_speaker_failure_does_not_auto_confirm()
    print(
        "PASS: prompt speech failure cannot bypass confirmation."
    )

    await test_confirmation_cannot_be_reused_after_interaction()
    print(
        "PASS: completed interaction cannot replay confirmation."
    )

    print()
    print(
        "PASS: complete VoiceAssistant interaction "
        "regression suite complete."
    )


if __name__ == "__main__":
    asyncio.run(
        main()
    )
