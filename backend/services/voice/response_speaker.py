"""Piper-backed spoken responses for Jarvis."""

from __future__ import annotations

from typing import Any

from backend.services.video.voice_generator import (
    VoiceGenerator,
)
from backend.services.voice.audio_player import (
    AudioPlayer,
)


class VoiceResponseSpeaker:
    """Generate and play one Jarvis response."""

    def __init__(
        self,
        *,
        voice_generator: Any | None = None,
        audio_player: Any | None = None,
    ) -> None:
        self.voice_generator = (
            voice_generator
            if voice_generator is not None
            else VoiceGenerator()
        )

        self.audio_player = (
            audio_player
            if audio_player is not None
            else AudioPlayer()
        )

    async def speak(
        self,
        text: str,
        *,
        filename: str = "jarvis_response",
    ) -> dict:
        spoken_text = " ".join(
            text.split()
        ).strip()

        if not spoken_text:
            return {
                "status": "silent",
                "text": "",
                "reason": "empty_response",
            }

        generated = (
            await self.voice_generator.generate(
                spoken_text,
                filename=filename,
            )
        )

        if not isinstance(
            generated,
            dict,
        ):
            raise RuntimeError(
                "Voice generator returned "
                "an invalid result."
            )

        if (
            generated.get("status")
            != "success"
        ):
            raise RuntimeError(
                "Voice generation did not "
                "complete successfully."
            )

        audio_path = generated.get(
            "audio_path"
        )

        if not audio_path:
            raise RuntimeError(
                "Voice generation returned "
                "no audio path."
            )

        playback = self.audio_player.play(
            audio_path
        )

        if not isinstance(
            playback,
            dict,
        ):
            raise RuntimeError(
                "Audio player returned "
                "an invalid result."
            )

        if (
            playback.get("status")
            != "success"
        ):
            raise RuntimeError(
                "Audio playback did not "
                "complete successfully."
            )

        return {
            "status": "success",
            "text": spoken_text,
            "audio_path": audio_path,
            "generation": generated,
            "playback": playback,
        }
