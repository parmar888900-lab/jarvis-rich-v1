"""Controlled execution boundary for Jarvis voice commands."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from backend.services.voice.command_router import (
    VoiceCommand,
)


@dataclass(frozen=True)
class VoiceExecutionResult:
    """Result of attempting to execute one parsed voice command."""

    status: str
    command_id: str | None
    agent: str | None
    task: str | None
    result: dict | None = None
    reason: str | None = None


class VoiceCommandExecutor:
    """Execute allowlisted voice commands through Commander."""

    _ALLOWED_TARGETS = frozenset(
        {
            ("youtube", "analyze_trends"),
            ("youtube", "create_video"),
            ("youtube", "upload_video"),
            ("goal", "list_goals"),
            ("goal", "get_goal_status"),
            ("goal", "create_goal"),
            ("goal", "update_goal"),
            ("goal", "pause_goal"),
            ("goal", "resume_goal"),
        }
    )

    _CONFIRMATION_TARGETS = frozenset(
        {
            ("youtube", "upload_video"),
            ("goal", "create_goal"),
            ("goal", "update_goal"),
            ("goal", "pause_goal"),
            ("goal", "resume_goal"),
        }
    )

    _FORBIDDEN_TARGETS = frozenset(
        {
            ("youtube", "publish_video"),
        }
    )

    def __init__(
        self,
        commander: Any,
    ) -> None:
        if commander is None:
            raise ValueError(
                "VoiceCommandExecutor requires a Commander."
            )

        route = getattr(
            commander,
            "route",
            None,
        )

        if route is None or not callable(route):
            raise ValueError(
                "Commander must provide a callable route method."
            )

        self.commander = commander

    async def execute(
        self,
        command: VoiceCommand,
        *,
        confirmed: bool = False,
    ) -> VoiceExecutionResult:
        """Execute one parsed command if policy permits it."""

        if not isinstance(
            command,
            VoiceCommand,
        ):
            return VoiceExecutionResult(
                status="blocked",
                command_id=None,
                agent=None,
                task=None,
                reason="invalid_voice_command_type",
            )

        if (
            command.status != "ready"
            or command.agent is None
            or command.task is None
        ):
            return VoiceExecutionResult(
                status="blocked",
                command_id=None,
                agent=command.agent,
                task=command.task,
                reason=(
                    command.reason
                    or "voice_command_not_ready"
                ),
            )

        target = (
            command.agent,
            command.task,
        )

        if target in self._FORBIDDEN_TARGETS:
            return VoiceExecutionResult(
                status="blocked",
                command_id=None,
                agent=command.agent,
                task=command.task,
                reason="forbidden_voice_target",
            )

        if target not in self._ALLOWED_TARGETS:
            return VoiceExecutionResult(
                status="blocked",
                command_id=None,
                agent=command.agent,
                task=command.task,
                reason="target_not_allowlisted",
            )

        policy_requires_confirmation = (
            target
            in self._CONFIRMATION_TARGETS
        )

        if (
            policy_requires_confirmation
            and not command.requires_confirmation
        ):
            return VoiceExecutionResult(
                status="blocked",
                command_id=None,
                agent=command.agent,
                task=command.task,
                reason="confirmation_policy_mismatch",
            )

        if (
            command.requires_confirmation
            and not confirmed
        ):
            return VoiceExecutionResult(
                status="confirmation_required",
                command_id=None,
                agent=command.agent,
                task=command.task,
                reason="explicit_confirmation_required",
            )

        command_id = (
            "voice-"
            + uuid4().hex
        )

        parameters = (
            dict(command.parameters)
            if command.parameters is not None
            else {}
        )

        result = await self.commander.route(
            agent=command.agent,
            task=command.task,
            command_id=command_id,
            parameters=parameters,
        )

        if not isinstance(
            result,
            dict,
        ):
            return VoiceExecutionResult(
                status="failed",
                command_id=command_id,
                agent=command.agent,
                task=command.task,
                reason="commander_returned_invalid_result",
            )

        return VoiceExecutionResult(
            status="completed",
            command_id=command_id,
            agent=command.agent,
            task=command.task,
            result=result,
        )
