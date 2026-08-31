import asyncio
from types import SimpleNamespace

from backend.services.voice.response_formatter import (
    VoiceResponseFormatter,
)
from backend.services.voice.response_speaker import (
    VoiceResponseSpeaker,
)


class FakeGenerator:
    def __init__(self):
        self.calls = []

    async def generate(
        self,
        script,
        filename="voice",
    ):
        self.calls.append(
            {
                "script": script,
                "filename": filename,
            }
        )

        return {
            "status": "success",
            "audio_path": "fake.wav",
            "duration": 1.0,
            "provider": "piper",
            "script": script,
        }


class FakePlayer:
    def __init__(self):
        self.calls = []

    def play(
        self,
        audio_path,
    ):
        self.calls.append(
            audio_path
        )

        return {
            "status": "success",
            "audio_path": audio_path,
            "duration": 1.0,
        }


def completed_result(
    payload,
    *,
    agent="youtube",
    task="analyze_trends",
):
    execution = SimpleNamespace(
        status="completed",
        result=payload,
    )

    return SimpleNamespace(
        status="completed",
        agent=agent,
        task=task,
        execution=execution,
    )


async def main():
    formatter = VoiceResponseFormatter()

    result = completed_result(
        {
            "status": "success",
            "final_trend_count": 10,
            "best_trend": {
                "title": (
                    "AI Generated Video "
                    "Technology"
                ),
            },
        }
    )

    response = formatter.format(
        result
    )

    assert (
        response
        == (
            "Trend analysis complete. "
            "I shortlisted 10 topics. "
            "The strongest candidate is "
            "AI Generated Video Technology."
        )
    )

    print(
        "PASS: successful trend result "
        "produces concise speech."
    )


    result = completed_result(
        {
            "status": "success",
            "final_trend_count": 7,
            "best_trend": {
                "trend": {
                    "topic": "Nested Topic",
                }
            },
        }
    )

    response = formatter.format(
        result
    )

    assert (
        "Nested Topic"
        in response
    )

    print(
        "PASS: nested trend title "
        "is supported."
    )


    result = completed_result(
        {
            "status": "success",
            "final_trend_count": 4,
            "best_trend": {
                "score": 90,
            },
        }
    )

    response = formatter.format(
        result
    )

    assert (
        response
        == (
            "Trend analysis complete. "
            "I shortlisted 4 "
            "production candidates."
        )
    )

    print(
        "PASS: unknown trend schema "
        "degrades safely."
    )


    result = completed_result(
        {
            "status": (
                "no_production_ready_topic"
            ),
            "final_trend_count": 10,
        }
    )

    response = formatter.format(
        result
    )

    assert (
        "none passed the production gate"
        in response
    )

    print(
        "PASS: production gate failure "
        "is represented accurately."
    )


    blocked = SimpleNamespace(
        status="blocked",
        agent=None,
        task=None,
        execution=None,
    )

    assert (
        "can't perform"
        in formatter.format(
            blocked
        )
    )

    print(
        "PASS: blocked command receives "
        "a safe spoken response."
    )


    wake_missing = SimpleNamespace(
        status="wake_not_detected",
        agent=None,
        task=None,
        execution=None,
    )

    assert (
        formatter.format(
            wake_missing
        )
        == ""
    )

    print(
        "PASS: ordinary speech produces "
        "no Jarvis response."
    )


    generator = FakeGenerator()
    player = FakePlayer()

    speaker = VoiceResponseSpeaker(
        voice_generator=generator,
        audio_player=player,
    )

    result = await speaker.speak(
        "Trend analysis complete.",
        filename="test_response",
    )

    assert result["status"] == "success"
    assert len(generator.calls) == 1
    assert len(player.calls) == 1

    assert (
        generator.calls[0]["script"]
        == "Trend analysis complete."
    )

    assert (
        generator.calls[0]["filename"]
        == "test_response"
    )

    assert (
        player.calls[0]
        == "fake.wav"
    )

    print(
        "PASS: response speaker connects "
        "TTS to playback."
    )


    result = await speaker.speak(
        "   "
    )

    assert result["status"] == "silent"

    assert len(generator.calls) == 1
    assert len(player.calls) == 1

    print(
        "PASS: empty response produces "
        "no TTS or playback."
    )


    print()
    print(
        "PASS: Jarvis voice response "
        "regression suite complete."
    )


asyncio.run(
    main()
)
