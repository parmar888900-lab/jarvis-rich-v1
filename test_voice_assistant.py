"""Regression tests for the Jarvis VoiceAssistant coordinator."""

import asyncio

from backend.services.voice.assistant import (
    VoiceAssistant,
)


class FakeCommander:
    def __init__(self):
        self.calls = []

    async def route(
        self,
        agent,
        task,
        command_id,
        parameters=None,
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
            "agent": agent,
            "task": task,
        }


class FakeTranscriber:
    def __init__(
        self,
        *,
        status="success",
        text="",
    ):
        self.status = status
        self.text = text

    def transcribe(
        self,
        audio_path,
    ):
        return {
            "status": self.status,
            "text": self.text,
        }


async def run_case(
    text,
    *,
    confirmed=False,
):
    commander = FakeCommander()

    assistant = VoiceAssistant(
        commander=commander,
        transcriber=FakeTranscriber(
            text=text
        ),
    )

    result = await assistant.process_audio(
        "fake.wav",
        confirmed=confirmed,
    )

    return (
        result,
        commander,
    )


async def main():
    result, commander = await run_case(
        "Hey Jarvis, analyze today's trends."
    )

    assert result.status == "completed"
    assert result.agent == "youtube"
    assert result.task == "analyze_trends"
    assert len(commander.calls) == 1

    print(
        "PASS: standard trend command completes."
    )


    result, commander = await run_case(
        "Hey Jarvis, analyze today's threads."
    )

    assert result.status == "completed"
    assert (
        result.command_text.lower()
        == "analyze today's trends."
    )
    assert result.task == "analyze_trends"
    assert len(commander.calls) == 1

    print(
        "PASS: observed threads/trends STT "
        "confusion is normalized narrowly."
    )


    result, commander = await run_case(
        "Analyze today's trends."
    )

    assert (
        result.status
        == "wake_not_detected"
    )
    assert len(commander.calls) == 0

    print(
        "PASS: command cannot bypass wake phrase."
    )


    result, commander = await run_case(
        "Hey Jarvis."
    )

    assert result.status == "wake_only"
    assert len(commander.calls) == 0

    print(
        "PASS: wake-only utterance does not execute."
    )


    result, commander = await run_case(
        "Hey Jarvis, upload the video."
    )

    assert (
        result.status
        == "confirmation_required"
    )
    assert result.requires_confirmation is True
    assert len(commander.calls) == 0

    print(
        "PASS: upload remains blocked pending confirmation."
    )


    result, commander = await run_case(
        "Hey Jarvis, upload the video.",
        confirmed=True,
    )

    assert result.status == "completed"
    assert result.task == "upload_video"
    assert len(commander.calls) == 1

    print(
        "PASS: confirmed upload may reach Commander."
    )


    result, commander = await run_case(
        "Hey Jarvis, publish the video.",
        confirmed=True,
    )

    assert result.status == "blocked"
    assert len(commander.calls) == 0

    print(
        "PASS: confirmation cannot authorize publication."
    )


    result, commander = await run_case(
        "Hey Jarvis, make the video public.",
        confirmed=True,
    )

    assert result.status == "blocked"
    assert len(commander.calls) == 0

    print(
        "PASS: public-release synonym remains blocked."
    )


    result, commander = await run_case(
        "Hey Jarvis, delete everything.",
        confirmed=True,
    )

    assert result.status == "unsupported"
    assert len(commander.calls) == 0

    print(
        "PASS: unsupported command never reaches Commander."
    )


    commander = FakeCommander()

    assistant = VoiceAssistant(
        commander=commander,
        transcriber=FakeTranscriber(
            status="no_speech",
            text="",
        ),
    )

    result = await assistant.process_audio(
        "fake.wav"
    )

    assert result.status == "no_speech"
    assert len(commander.calls) == 0

    print(
        "PASS: no-speech result fails closed."
    )


    assert (
        VoiceAssistant._normalize_observed_stt(
            "tell me about threads"
        )
        == "tell me about threads"
    )

    assert (
        VoiceAssistant._normalize_observed_stt(
            "upload today's threads"
        )
        == "upload today's threads"
    )

    print(
        "PASS: STT normalization is not general fuzzy matching."
    )


    print()
    print(
        "PASS: VoiceAssistant coordinator "
        "regression suite complete."
    )


if __name__ == "__main__":
    asyncio.run(
        main()
    )
