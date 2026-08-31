"""High-level coordinator for Jarvis voice commands."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from backend.services.commander import Commander
from backend.services.voice.command_executor import (
    VoiceCommandExecutor,
    VoiceExecutionResult,
)
from backend.services.voice.command_router import (
    VoiceCommandRouter,
)
from backend.services.voice.transcriber import (
    WhisperTranscriber,
)
from backend.services.voice.wake_phrase import (
    WakePhraseParser,
)


@dataclass(frozen=True)
class VoiceAssistantResult:
    """Result of processing one voice utterance."""

    status: str
    transcript: str
    command_text: str
    agent: str | None = None
    task: str | None = None
    requires_confirmation: bool = False
    execution: VoiceExecutionResult | None = None
    reason: str | None = None


class VoiceAssistant:
    """Coordinate STT, wake detection, routing, and execution."""

    def __init__(
        self,
        *,
        commander: Any | None = None,
        transcriber: Any | None = None,
        wake_parser: Any | None = None,
        router: Any | None = None,
        executor: Any | None = None,
    ) -> None:
        self.commander = (
            commander
            if commander is not None
            else Commander()
        )

        self.transcriber = (
            transcriber
            if transcriber is not None
            else WhisperTranscriber(
                model_name="base.en"
            )
        )

        self.wake_parser = (
            wake_parser
            if wake_parser is not None
            else WakePhraseParser()
        )

        self.router = (
            router
            if router is not None
            else VoiceCommandRouter()
        )

        self.executor = (
            executor
            if executor is not None
            else VoiceCommandExecutor(
                self.commander
            )
        )

    async def process_audio(
        self,
        audio_path: str | Path,
        *,
        confirmed: bool = False,
    ) -> VoiceAssistantResult:
        """Process one audio file through the safe voice pipeline."""

        transcription = self.transcriber.transcribe(
            audio_path
        )

        transcription_status = transcription.get(
            "status"
        )

        transcript = str(
            transcription.get(
                "text",
                "",
            )
            or ""
        ).strip()

        if transcription_status != "success":
            return VoiceAssistantResult(
                status="no_speech",
                transcript=transcript,
                command_text="",
                reason="transcription_not_successful",
            )

        wake = self.wake_parser.parse(
            transcript
        )

        if not wake.detected:
            return VoiceAssistantResult(
                status="wake_not_detected",
                transcript=transcript,
                command_text="",
                reason="wake_phrase_not_detected",
            )

        command_text = self._normalize_observed_stt(
            wake.command
        )

        if not command_text:
            return VoiceAssistantResult(
                status="wake_only",
                transcript=transcript,
                command_text="",
                reason="wake_phrase_without_command",
            )

        command = self.router.parse(
            command_text
        )

        if command.status != "ready":
            return VoiceAssistantResult(
                status=command.status,
                transcript=transcript,
                command_text=command_text,
                agent=command.agent,
                task=command.task,
                requires_confirmation=(
                    command.requires_confirmation
                ),
                reason=command.reason,
            )

        execution = await self.executor.execute(
            command,
            confirmed=confirmed,
        )

        if execution.status == "confirmation_required":
            return VoiceAssistantResult(
                status="confirmation_required",
                transcript=transcript,
                command_text=command_text,
                agent=command.agent,
                task=command.task,
                requires_confirmation=True,
                execution=execution,
                reason=execution.reason,
            )

        if execution.status != "completed":
            return VoiceAssistantResult(
                status="execution_failed",
                transcript=transcript,
                command_text=command_text,
                agent=command.agent,
                task=command.task,
                requires_confirmation=(
                    command.requires_confirmation
                ),
                execution=execution,
                reason=execution.reason,
            )

        return VoiceAssistantResult(
            status="completed",
            transcript=transcript,
            command_text=command_text,
            agent=command.agent,
            task=command.task,
            requires_confirmation=(
                command.requires_confirmation
            ),
            execution=execution,
        )

    @staticmethod
    def _normalize_observed_stt(
        command_text: str | None,
    ) -> str:
        """Normalize only narrow, observed STT confusions."""

        text = str(
            command_text
            or ""
        ).strip()

        lowered = text.lower()

        aliases = {
            "analyze today's threads":
                "analyze today's trends",
            "analyze today's threads.":
                "analyze today's trends.",
            "analyse today's threads":
                "analyse today's trends",
            "analyse today's threads.":
                "analyse today's trends.",
        }

        return aliases.get(
            lowered,
            text,
        )
