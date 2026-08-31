"""High-level coordinator for Jarvis voice commands."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from backend.services.commander import Commander
from backend.services.voice.audio_capture import (
    AudioCapture,
)
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
from backend.services.voice.confirmation import (
    VoiceConfirmationManager,
)
from backend.services.voice.response_formatter import VoiceResponseFormatter
from backend.services.voice.response_speaker import VoiceResponseSpeaker


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





@dataclass(frozen=True)
class VoiceAssistantResponse:
    """Combined command and user-response result."""

    assistant_result: VoiceAssistantResult
    response_text: str
    speech_status: str
    speech: dict | None = None
    speech_reason: str | None = None

    @property
    def status(self) -> str:
        """Preserve the authoritative command status."""

        return self.assistant_result.status


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
        audio_capture: Any | None = None,
        response_formatter: Any | None = None,
        response_speaker: Any | None = None,
        confirmation_manager: Any | None = None,
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

        self.audio_capture = (
            audio_capture
            if audio_capture is not None
            else AudioCapture()
        )

        self.response_formatter = (
            response_formatter
            if response_formatter is not None
            else VoiceResponseFormatter()
        )

        self.response_speaker = (
            response_speaker
            if response_speaker is not None
            else VoiceResponseSpeaker()
        )

        self.confirmation_manager = (
            confirmation_manager
            if confirmation_manager is not None
            else VoiceConfirmationManager()
        )




    async def listen_for_confirmation(
        self,
        audio_path: str | Path,
        *,
        duration_seconds: float = 4.0,
        on_ready=None,
    ) -> VoiceAssistantResult:
        """Capture and resolve one pending confirmation utterance."""

        # Do not open the microphone unless a valid,
        # unexpired confirmation is actually pending.
        if not self.confirmation_manager.has_pending:
            return VoiceAssistantResult(
                status="confirmation_not_pending",
                transcript="",
                command_text="",
                reason="no_pending_confirmation",
            )

        try:
            capture_result = self.audio_capture.record(
                audio_path,
                duration_seconds=duration_seconds,
                on_ready=on_ready,
            )
        except Exception as exc:
            self.confirmation_manager.clear()

            return VoiceAssistantResult(
                status="capture_failed",
                transcript="",
                command_text="",
                reason=(
                    "confirmation_audio_capture_exception:"
                    f"{type(exc).__name__}"
                ),
            )

        if not isinstance(
            capture_result,
            dict,
        ):
            self.confirmation_manager.clear()

            return VoiceAssistantResult(
                status="capture_failed",
                transcript="",
                command_text="",
                reason=(
                    "invalid_confirmation_audio_capture_result"
                ),
            )

        if (
            capture_result.get("status")
            != "success"
        ):
            self.confirmation_manager.clear()

            return VoiceAssistantResult(
                status="capture_failed",
                transcript="",
                command_text="",
                reason=str(
                    capture_result.get(
                        "reason",
                        "confirmation_audio_capture_not_successful",
                    )
                ),
            )

        try:
            transcription = self.transcriber.transcribe(
                audio_path
            )
        except Exception as exc:
            self.confirmation_manager.clear()

            return VoiceAssistantResult(
                status="no_speech",
                transcript="",
                command_text="",
                reason=(
                    "confirmation_transcription_exception:"
                    f"{type(exc).__name__}"
                ),
            )

        if not isinstance(
            transcription,
            dict,
        ):
            self.confirmation_manager.clear()

            return VoiceAssistantResult(
                status="no_speech",
                transcript="",
                command_text="",
                reason=(
                    "invalid_confirmation_transcription_result"
                ),
            )

        transcript = str(
            transcription.get(
                "text",
                "",
            )
            or ""
        ).strip()

        if (
            transcription.get("status")
            != "success"
            or not transcript
        ):
            self.confirmation_manager.clear()

            return VoiceAssistantResult(
                status="no_speech",
                transcript=transcript,
                command_text="",
                reason=(
                    "confirmation_transcription_not_successful"
                ),
            )

        # Deliberately no wake-phrase parsing here.
        # The assistant already requested confirmation,
        # and the confirmation manager accepts only its
        # narrow confirmation/cancellation vocabulary.
        return await self.resolve_confirmation(
            transcript
        )

    async def resolve_confirmation(
        self,
        transcript: str | None,
    ) -> VoiceAssistantResult:
        """Resolve and execute one pending voice confirmation."""

        decision = self.confirmation_manager.resolve(
            transcript
        )

        normalized_transcript = str(
            transcript
            or ""
        ).strip()

        if decision.status == "no_pending":
            return VoiceAssistantResult(
                status="confirmation_not_pending",
                transcript=normalized_transcript,
                command_text="",
                reason=decision.reason,
            )

        if decision.status == "expired":
            return VoiceAssistantResult(
                status="confirmation_expired",
                transcript=normalized_transcript,
                command_text="",
                reason=decision.reason,
            )

        if decision.status == "cancelled":
            return VoiceAssistantResult(
                status="confirmation_cancelled",
                transcript=normalized_transcript,
                command_text="",
                reason=decision.reason,
            )

        if decision.status == "blocked":
            return VoiceAssistantResult(
                status="blocked",
                transcript=normalized_transcript,
                command_text="",
                reason=decision.reason,
            )

        if decision.status != "confirmed":
            return VoiceAssistantResult(
                status="confirmation_rejected",
                transcript=normalized_transcript,
                command_text="",
                reason=(
                    decision.reason
                    or "confirmation_not_understood"
                ),
            )

        command = decision.command

        if command is None:
            return VoiceAssistantResult(
                status="execution_failed",
                transcript=normalized_transcript,
                command_text="",
                reason="confirmed_command_missing",
            )

        execution = await self.executor.execute(
            command,
            confirmed=True,
        )

        if execution.status != "completed":
            return VoiceAssistantResult(
                status="execution_failed",
                transcript=normalized_transcript,
                command_text=command.transcript,
                agent=command.agent,
                task=command.task,
                requires_confirmation=True,
                execution=execution,
                reason=execution.reason,
            )

        return VoiceAssistantResult(
            status="completed",
            transcript=normalized_transcript,
            command_text=command.transcript,
            agent=command.agent,
            task=command.task,
            requires_confirmation=True,
            execution=execution,
        )


    async def _respond_to_result(
        self,
        assistant_result: VoiceAssistantResult,
        *,
        response_filename: str = "jarvis_response",
    ) -> VoiceAssistantResponse:
        """Format and attempt speech without changing command status."""

        try:
            response_text = self.response_formatter.format(
                assistant_result
            )
        except Exception as exc:
            return VoiceAssistantResponse(
                assistant_result=assistant_result,
                response_text="",
                speech_status="not_attempted",
                speech_reason=(
                    "response_format_exception:"
                    f"{type(exc).__name__}"
                ),
            )

        response_text = str(
            response_text
            or ""
        ).strip()

        if not response_text:
            return VoiceAssistantResponse(
                assistant_result=assistant_result,
                response_text="",
                speech_status="silent",
                speech_reason="empty_response",
            )

        try:
            speech = await self.response_speaker.speak(
                response_text,
                filename=response_filename,
            )
        except Exception as exc:
            return VoiceAssistantResponse(
                assistant_result=assistant_result,
                response_text=response_text,
                speech_status="failed",
                speech_reason=(
                    "speech_exception:"
                    f"{type(exc).__name__}"
                ),
            )

        if not isinstance(
            speech,
            dict,
        ):
            return VoiceAssistantResponse(
                assistant_result=assistant_result,
                response_text=response_text,
                speech_status="failed",
                speech_reason="invalid_speech_result",
            )

        speech_status = str(
            speech.get(
                "status",
                "failed",
            )
        )

        if speech_status not in {
            "success",
            "silent",
        }:
            return VoiceAssistantResponse(
                assistant_result=assistant_result,
                response_text=response_text,
                speech_status="failed",
                speech=speech,
                speech_reason=str(
                    speech.get(
                        "reason",
                        "speech_not_successful",
                    )
                ),
            )

        return VoiceAssistantResponse(
            assistant_result=assistant_result,
            response_text=response_text,
            speech_status=speech_status,
            speech=speech,
        )

    async def respond_once(
        self,
        audio_path: str | Path,
        *,
        duration_seconds: float = 5.0,
        confirmed: bool = False,
        on_ready=None,
        response_filename: str = "jarvis_response",
    ) -> VoiceAssistantResponse:
        """Listen, execute, format, and attempt a spoken response."""

        assistant_result = await self.listen_once(
            audio_path,
            duration_seconds=duration_seconds,
            confirmed=confirmed,
            on_ready=on_ready,
        )

        return await self._respond_to_result(
            assistant_result,
            response_filename=response_filename,
        )


    async def interact_once(
        self,
        audio_path: str | Path,
        *,
        confirmation_audio_path: str | Path | None = None,
        duration_seconds: float = 5.0,
        confirmation_duration_seconds: float = 4.0,
        on_ready=None,
        on_confirmation_ready=None,
        response_filename: str = "jarvis_response",
        confirmation_response_filename: str = (
            "jarvis_confirmation_response"
        ),
    ) -> VoiceAssistantResponse:
        """Run one complete voice interaction, including confirmation."""

        first_response = await self.respond_once(
            audio_path,
            duration_seconds=duration_seconds,
            confirmed=False,
            on_ready=on_ready,
            response_filename=response_filename,
        )

        if (
            first_response.assistant_result.status
            != "confirmation_required"
        ):
            return first_response

        if confirmation_audio_path is None:
            self.confirmation_manager.clear()

            missing_result = VoiceAssistantResult(
                status="confirmation_cancelled",
                transcript="",
                command_text=(
                    first_response
                    .assistant_result
                    .command_text
                ),
                agent=(
                    first_response
                    .assistant_result
                    .agent
                ),
                task=(
                    first_response
                    .assistant_result
                    .task
                ),
                requires_confirmation=True,
                reason="confirmation_audio_path_required",
            )

            return await self._respond_to_result(
                missing_result,
                response_filename=(
                    confirmation_response_filename
                ),
            )

        confirmation_result = (
            await self.listen_for_confirmation(
                confirmation_audio_path,
                duration_seconds=(
                    confirmation_duration_seconds
                ),
                on_ready=on_confirmation_ready,
            )
        )

        return await self._respond_to_result(
            confirmation_result,
            response_filename=(
                confirmation_response_filename
            ),
        )

    async def listen_once(
        self,
        audio_path: str | Path,
        *,
        duration_seconds: float = 5.0,
        confirmed: bool = False,
        on_ready=None,
    ) -> VoiceAssistantResult:
        """Capture and process one synchronized microphone utterance."""

        try:
            capture_result = self.audio_capture.record(
                audio_path,
                duration_seconds=duration_seconds,
                on_ready=on_ready,
            )
        except Exception as exc:
            return VoiceAssistantResult(
                status="capture_failed",
                transcript="",
                command_text="",
                reason=(
                    "audio_capture_exception:"
                    f"{type(exc).__name__}"
                ),
            )

        if not isinstance(
            capture_result,
            dict,
        ):
            return VoiceAssistantResult(
                status="capture_failed",
                transcript="",
                command_text="",
                reason="invalid_audio_capture_result",
            )

        if (
            capture_result.get("status")
            != "success"
        ):
            return VoiceAssistantResult(
                status="capture_failed",
                transcript="",
                command_text="",
                reason=(
                    str(
                        capture_result.get(
                            "reason",
                            "audio_capture_not_successful",
                        )
                    )
                ),
            )

        return await self.process_audio(
            audio_path,
            confirmed=confirmed,
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
            pending = self.confirmation_manager.request(
                command
            )

            if pending.status != "pending":
                return VoiceAssistantResult(
                    status="execution_failed",
                    transcript=transcript,
                    command_text=command_text,
                    agent=command.agent,
                    task=command.task,
                    requires_confirmation=True,
                    execution=execution,
                    reason=(
                        pending.reason
                        or "confirmation_state_failed"
                    ),
                )

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
