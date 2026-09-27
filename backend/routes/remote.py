"""Authenticated natural-language remote control for Jarvis."""

from __future__ import annotations

import tempfile
import asyncio
from uuid import uuid4
from types import SimpleNamespace
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from backend.services.commander import Commander
from backend.services.remote_auth import require_remote_token
from backend.services.voice.command_executor import VoiceCommandExecutor
from backend.services.voice.command_router import VoiceCommandRouter
from backend.services.voice.transcriber import WhisperTranscriber
from backend.services.voice.wake_phrase import WakePhraseParser
from backend.services.voice.response_formatter import VoiceResponseFormatter
from backend.database import async_session
from backend.services.network.voice_commands import route_network_command
from backend.services.video.voice_generator import VoiceGenerator


router = APIRouter(
    prefix="/remote",
    tags=["remote"],
    dependencies=[Depends(require_remote_token)],
)

commander = Commander()
command_router = VoiceCommandRouter()
command_executor = VoiceCommandExecutor(commander)
voice_transcriber = WhisperTranscriber(
    model_name="tiny.en"
)

MAX_REMOTE_AUDIO_BYTES = 20 * 1024 * 1024
speech_lock = asyncio.Lock()
wake_parser = WakePhraseParser()
voice_formatter = VoiceResponseFormatter()


class RemoteCommandRequest(BaseModel):
    """Natural-language command submitted by a remote client."""

    command: str = Field(
        ...,
        min_length=1,
        max_length=500,
    )


class SpeechRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=500)


@router.post("/speech")
async def remote_piper_speech(payload: SpeechRequest):
    """Generate a bounded British Piper response for the authenticated owner."""
    async with speech_lock:
        try:
            result = await VoiceGenerator().generate(
                payload.text, filename=f"jarvis_remote_{uuid4().hex}")
        except (OSError, RuntimeError, TimeoutError) as exc:
            raise HTTPException(status_code=503, detail=f"Piper unavailable: {type(exc).__name__}") from None
    path = Path(result["audio_path"])
    return FileResponse(path, media_type="audio/wav",
                        background=BackgroundTask(path.unlink, missing_ok=True))


async def _execute_command_text(
    command: str,
) -> dict:
    """Parse and safely execute one natural-language command."""

    network = await route_network_command(command, async_session, root=Path.cwd())
    if network is not None:
        return network

    parsed = command_router.parse(
        command
    )

    if parsed.status != "ready":
        return {
            "status": parsed.status,
            "command": parsed.transcript,
            "agent": parsed.agent,
            "task": parsed.task,
            "requires_confirmation": (
                parsed.requires_confirmation
            ),
            "reason": parsed.reason,
        }

    execution = await command_executor.execute(
        parsed,
        confirmed=False,
    )

    return {
        "status": execution.status,
        "command": parsed.transcript,
        "command_id": execution.command_id,
        "agent": execution.agent,
        "task": execution.task,
        "requires_confirmation": (
            parsed.requires_confirmation
        ),
        "result": execution.result,
        "reason": execution.reason,
    }


async def _route_manual_voice(transcript: str) -> dict:
    """The button accepts natural commands and honors either wake activation."""
    wake = wake_parser.parse(transcript)
    if wake.detected and not wake.command:
        result = SimpleNamespace(status="wake_only", wake_variant=wake.variant)
        return {"status": "greeting", "message": voice_formatter.format(result),
                "transcript": transcript}
    command = wake.command if wake.detected else transcript
    result = await _execute_command_text(command)
    if wake.variant == "special_home":
        greeting = voice_formatter.format(SimpleNamespace(
            status="wake_only", wake_variant="special_home"))
        result["message"] = f"{greeting} {result.get('message') or voice_formatter.format(SimpleNamespace(**result))}"
    else:
        result["message"] = voice_formatter.format(SimpleNamespace(**result))
    return result


def _audio_suffix(
    content_type: str,
) -> str:
    """Choose a temporary suffix FFmpeg/Whisper can understand."""

    clean = (
        str(content_type or "")
        .split(";", 1)[0]
        .strip()
        .lower()
    )

    mapping = {
        "audio/wav": ".wav",
        "audio/x-wav": ".wav",
        "audio/mpeg": ".mp3",
        "audio/mp3": ".mp3",
        "audio/mp4": ".m4a",
        "audio/x-m4a": ".m4a",
        "audio/aac": ".aac",
        "audio/webm": ".webm",
        "video/webm": ".webm",
        "video/mp4": ".mp4",
        "video/quicktime": ".mov",
    }

    return mapping.get(
        clean,
        ".m4a",
    )


@router.post("/command")
async def remote_command(
    payload: RemoteCommandRequest,
):
    """Parse and safely execute one natural-language command."""

    return await _execute_command_text(
        payload.command
    )


@router.post("/voice")
async def remote_voice(
    request: Request,
):
    """
    Receive one recorded command, transcribe it with Whisper,
    and pass the transcript through the normal safe command path.
    """

    content_length = request.headers.get(
        "content-length"
    )

    if content_length:
        try:
            declared_size = int(
                content_length
            )
        except ValueError:
            declared_size = 0

        if (
            declared_size >
            MAX_REMOTE_AUDIO_BYTES
        ):
            raise HTTPException(
                status_code=413,
                detail="Voice recording is too large.",
            )

    audio_bytes = await request.body()

    if not audio_bytes:
        raise HTTPException(
            status_code=400,
            detail="No audio recording received.",
        )

    if (
        len(audio_bytes) >
        MAX_REMOTE_AUDIO_BYTES
    ):
        raise HTTPException(
            status_code=413,
            detail="Voice recording is too large.",
        )

    content_type = request.headers.get(
        "content-type",
        "",
    )

    suffix = _audio_suffix(
        content_type
    )

    temp_path: Path | None = None

    try:
        with tempfile.NamedTemporaryFile(
            prefix="jarvis_remote_voice_",
            suffix=suffix,
            delete=False,
        ) as temp_file:
            temp_file.write(
                audio_bytes
            )

            temp_path = Path(
                temp_file.name
            )

        transcription = await run_in_threadpool(
            voice_transcriber.transcribe,
            temp_path,
        )

        transcript = str(
            transcription.get("text")
            or ""
        ).strip()

        if not transcript:
            return {
                "status": "no_speech",
                "transcript": "",
                "reason": (
                    "Whisper did not detect a spoken command."
                ),
            }

        if len(transcript) > 500:
            return {
                "status": "unsupported",
                "transcript": transcript[:500],
                "reason": (
                    "Transcribed command is too long."
                ),
            }

        result = await _route_manual_voice(
            transcript
        )

        result["transcript"] = transcript
        result["transcription"] = {
            "status": transcription.get(
                "status"
            ),
            "model": transcription.get(
                "model"
            ),
            "language": transcription.get(
                "language"
            ),
        }

        return result

    finally:
        if (
            temp_path is not None
            and temp_path.exists()
        ):
            try:
                temp_path.unlink()
            except OSError:
                pass
