"""Short-lived, single-use voice confirmation state."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Callable

from backend.services.voice.command_router import (
    VoiceCommand,
)


@dataclass(frozen=True)
class VoiceConfirmationDecision:
    """Result of interpreting one confirmation response."""

    status: str
    transcript: str
    command: VoiceCommand | None = None
    reason: str | None = None


@dataclass(frozen=True)
class _PendingConfirmation:
    command: VoiceCommand
    expires_at: float


class VoiceConfirmationManager:
    """Hold one short-lived confirmation-required command."""

    _CONFIRM_PATTERNS = (
        r"^confirm$",
        r"^yes(?:\s+confirm)?$",
        r"^confirm\s+(?:it|that)$",
        r"^yes\s+do\s+it$",
        r"^proceed$",
    )

    _CANCEL_PATTERNS = (
        r"^cancel$",
        r"^no$",
        r"^no\s+cancel$",
        r"^cancel\s+(?:it|that)$",
        r"^do\s+not\s+proceed$",
        r"^don't\s+proceed$",
    )

    _PUBLICATION_PATTERNS = (
        r"\bpublish\b",
        r"\bpublic\b",
        r"\bgo\s+public\b",
    )

    def __init__(
        self,
        *,
        timeout_seconds: float = 15.0,
        clock: Callable[[], float] | None = None,
    ) -> None:
        if (
            isinstance(
                timeout_seconds,
                bool,
            )
            or not isinstance(
                timeout_seconds,
                (int, float),
            )
            or timeout_seconds <= 0
        ):
            raise ValueError(
                "timeout_seconds must be positive."
            )

        self.timeout_seconds = float(
            timeout_seconds
        )

        self._clock = (
            clock
            if clock is not None
            else time.monotonic
        )

        if not callable(
            self._clock
        ):
            raise ValueError(
                "clock must be callable."
            )

        self._pending: (
            _PendingConfirmation | None
        ) = None

    @property
    def has_pending(self) -> bool:
        """Return whether an unexpired command is pending."""

        self._expire_if_needed()

        return self._pending is not None

    def request(
        self,
        command: VoiceCommand,
    ) -> VoiceConfirmationDecision:
        """Store one exact confirmation-required command."""

        if not isinstance(
            command,
            VoiceCommand,
        ):
            self.clear()

            return VoiceConfirmationDecision(
                status="blocked",
                transcript="",
                reason="invalid_voice_command_type",
            )

        if (
            command.status != "ready"
            or command.agent is None
            or command.task is None
        ):
            self.clear()

            return VoiceConfirmationDecision(
                status="blocked",
                transcript=command.transcript,
                reason="voice_command_not_ready",
            )

        if not command.requires_confirmation:
            self.clear()

            return VoiceConfirmationDecision(
                status="blocked",
                transcript=command.transcript,
                reason="confirmation_not_required",
            )

        target = (
            command.agent,
            command.task,
        )

        # Defense in depth. Publication must never become
        # confirmable through this state machine.
        if target == (
            "youtube",
            "publish_video",
        ):
            self.clear()

            return VoiceConfirmationDecision(
                status="blocked",
                transcript=command.transcript,
                reason="forbidden_voice_target",
            )

        self._pending = _PendingConfirmation(
            command=command,
            expires_at=(
                self._clock()
                + self.timeout_seconds
            ),
        )

        return VoiceConfirmationDecision(
            status="pending",
            transcript=command.transcript,
            command=command,
        )

    def resolve(
        self,
        transcript: str | None,
    ) -> VoiceConfirmationDecision:
        """Resolve the current pending command exactly once."""

        normalized = self._normalize(
            transcript
        )

        pending = self._pending

        if pending is None:
            return VoiceConfirmationDecision(
                status="no_pending",
                transcript=normalized,
                reason="no_pending_confirmation",
            )

        if self._is_expired(
            pending
        ):
            self.clear()

            return VoiceConfirmationDecision(
                status="expired",
                transcript=normalized,
                reason="confirmation_expired",
            )

        # Any publication language blocks and consumes the
        # pending operation. A phrase such as
        # "confirm and make it public" can never authorize
        # the original command or create a new one.
        if self._matches_any(
            normalized,
            self._PUBLICATION_PATTERNS,
        ):
            self.clear()

            return VoiceConfirmationDecision(
                status="blocked",
                transcript=normalized,
                reason=(
                    "public_release_not_available_by_voice"
                ),
            )

        if self._matches_any(
            normalized,
            self._CANCEL_PATTERNS,
        ):
            self.clear()

            return VoiceConfirmationDecision(
                status="cancelled",
                transcript=normalized,
                reason="confirmation_cancelled",
            )

        if self._matches_any(
            normalized,
            self._CONFIRM_PATTERNS,
        ):
            command = pending.command

            # Consume before execution. Even if execution
            # later fails, the confirmation cannot be replayed.
            self.clear()

            return VoiceConfirmationDecision(
                status="confirmed",
                transcript=normalized,
                command=command,
            )

        # Unknown speech fails closed and consumes the pending
        # confirmation rather than keeping authorization alive.
        self.clear()

        return VoiceConfirmationDecision(
            status="rejected",
            transcript=normalized,
            reason="confirmation_not_understood",
        )

    def clear(self) -> None:
        """Discard any pending confirmation."""

        self._pending = None

    def _expire_if_needed(self) -> None:
        pending = self._pending

        if (
            pending is not None
            and self._is_expired(
                pending
            )
        ):
            self.clear()

    def _is_expired(
        self,
        pending: _PendingConfirmation,
    ) -> bool:
        return (
            self._clock()
            >= pending.expires_at
        )

    @staticmethod
    def _normalize(
        text: str | None,
    ) -> str:
        normalized = str(
            text
            or ""
        ).strip().lower()

        normalized = re.sub(
            r"\s+",
            " ",
            normalized,
        )

        return normalized.strip(
            " \t\r\n.,!?;:"
        )

    @staticmethod
    def _matches_any(
        transcript: str,
        patterns: tuple[str, ...],
    ) -> bool:
        return any(
            re.search(
                pattern,
                transcript,
                flags=re.IGNORECASE,
            )
            is not None
            for pattern in patterns
        )
