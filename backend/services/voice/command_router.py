"""Safe natural-language routing for Jarvis voice commands."""

from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class VoiceCommand:
    """A parsed voice command with no execution authority."""

    status: str
    transcript: str
    agent: str | None = None
    task: str | None = None
    parameters: dict | None = None
    requires_confirmation: bool = False
    reason: str | None = None

    @property
    def executable(self) -> bool:
        return (
            self.status == "ready"
            and self.agent is not None
            and self.task is not None
        )


class VoiceCommandRouter:
    """Map recognized speech onto a narrow Commander allowlist."""

    _PUBLICATION_PATTERNS = (
        r"\bpublish\b",
        r"\bmake\s+(?:it|the\s+video)\s+public\b",
        r"\bset\s+(?:it|the\s+video)\s+(?:to\s+)?public\b",
        r"\bchange\s+(?:it|the\s+video)\s+(?:to\s+)?public\b",
        r"\bgo\s+public\b",
    )

    _ANALYZE_TRENDS_PATTERNS = (
        r"\banaly[sz]e(?:\s+today'?s)?\s+trends?\b",
        r"\bcheck(?:\s+today'?s)?\s+trends?\b",
        r"\bwhat(?:'s|\s+is)\s+trending\b",
    )

    _SYSTEM_STATUS_PATTERNS = (
        r"\bjarvis\s+status\b",
        r"\bsystem\s+status\b",
        r"\bwhat(?:'s|\s+is)\s+(?:the\s+)?progress\b",
        r"\bhow\s+many\s+videos?\s+(?:have\s+we\s+made|are\s+done|have\s+been\s+made|did\s+we\s+make)\b",
        r"\bhow\s+(?:are|is)\s+(?:the\s+)?analytics\b",
        r"\bhow\s+is\s+(?:the\s+)?channel\s+doing\b",
        r"\bwhat\s+happened\s+in\s+(?:the\s+)?last\s+production\s+cycle\b",
        r"\bgive\s+me\s+(?:an?\s+)?update\b",
    )

    _CREATE_VIDEO_PATTERNS = (
        r"\bcreate\s+(?:a\s+)?video\b",
        r"\bmake\s+(?:a\s+)?video\b",
        r"\bgenerate\s+(?:a\s+)?video\b",
    )

    _UPLOAD_VIDEO_PATTERNS = (
        r"\bupload\s+(?:the\s+|this\s+|a\s+)?video\b",
        r"\bupload\s+(?:the\s+|this\s+)?short\b",
    )

    _LIST_GOALS_PATTERNS = (
        r"\blist(?:\s+my)?\s+goals?\b",
        r"\bshow(?:\s+me)?(?:\s+my)?\s+goals?\b",
        r"\bwhat\s+are\s+my\s+goals?\b",
    )

    _GOAL_STATUS_PATTERNS = (
        r"\bgoal\s+status\b",
        r"\bstatus\s+of\s+(?:my\s+)?goals?\b",
        r"\bhow\s+are\s+(?:my\s+)?goals?\s+doing\b",
    )

    _GOAL_MUTATION_WORDS = frozenset(
        {
            "create",
            "update",
            "pause",
            "resume",
        }
    )

    _ALLOWED_TARGETS = frozenset(
        {
            ("youtube", "analyze_trends"),
            ("youtube", "create_video"),
            ("youtube", "upload_video"),
            ("system", "get_status"),
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

    def parse(
        self,
        command_text: str | None,
    ) -> VoiceCommand:
        """Interpret one wake-phrase-stripped command."""

        transcript = self._normalize(
            command_text
        )

        if not transcript:
            return VoiceCommand(
                status="unsupported",
                transcript="",
                reason="empty_command",
            )

        if self._matches_any(
            transcript,
            self._PUBLICATION_PATTERNS,
        ):
            return VoiceCommand(
                status="blocked",
                transcript=transcript,
                reason="public_release_not_available_by_voice",
            )

        candidates: list[
            tuple[str, str, dict | None]
        ] = []

        if self._matches_any(
            transcript,
            self._ANALYZE_TRENDS_PATTERNS,
        ):
            candidates.append(
                (
                    "youtube",
                    "analyze_trends",
                    None,
                )
            )

        if self._matches_any(
            transcript,
            self._SYSTEM_STATUS_PATTERNS,
        ):
            candidates.append(
                (
                    "system",
                    "get_status",
                    None,
                )
            )

        if self._matches_any(
            transcript,
            self._CREATE_VIDEO_PATTERNS,
        ):
            candidates.append(
                (
                    "youtube",
                    "create_video",
                    None,
                )
            )

        if self._matches_any(
            transcript,
            self._UPLOAD_VIDEO_PATTERNS,
        ):
            candidates.append(
                (
                    "youtube",
                    "upload_video",
                    None,
                )
            )

        if self._matches_any(
            transcript,
            self._LIST_GOALS_PATTERNS,
        ):
            candidates.append(
                (
                    "goal",
                    "list_goals",
                    None,
                )
            )

        if self._matches_any(
            transcript,
            self._GOAL_STATUS_PATTERNS,
        ):
            candidates.append(
                (
                    "goal",
                    "get_goal_status",
                    None,
                )
            )

        mutation = self._parse_goal_mutation(
            transcript
        )

        if mutation is not None:
            candidates.append(
                mutation
            )

        unique = []

        for candidate in candidates:
            if candidate not in unique:
                unique.append(
                    candidate
                )

        if not unique:
            return VoiceCommand(
                status="unsupported",
                transcript=transcript,
                reason="command_not_allowlisted",
            )

        if len(unique) != 1:
            return VoiceCommand(
                status="ambiguous",
                transcript=transcript,
                reason="multiple_commands_detected",
            )

        agent, task, parameters = unique[0]

        target = (
            agent,
            task,
        )

        if target not in self._ALLOWED_TARGETS:
            return VoiceCommand(
                status="blocked",
                transcript=transcript,
                reason="target_not_allowlisted",
            )

        requires_confirmation = (
            target
            in self._CONFIRMATION_TARGETS
        )

        return VoiceCommand(
            status="ready",
            transcript=transcript,
            agent=agent,
            task=task,
            parameters=parameters,
            requires_confirmation=requires_confirmation,
        )

    def _parse_goal_mutation(
        self,
        transcript: str,
    ) -> tuple[str, str, dict | None] | None:
        words = set(
            re.findall(
                r"[a-z0-9]+",
                transcript,
            )
        )

        if "goal" not in words and "goals" not in words:
            return None

        actions = (
            words
            & self._GOAL_MUTATION_WORDS
        )

        if len(actions) != 1:
            return None

        action = next(
            iter(actions)
        )

        task = {
            "create": "create_goal",
            "update": "update_goal",
            "pause": "pause_goal",
            "resume": "resume_goal",
        }[action]

        # Parameters are intentionally not inferred here.
        # Goal mutation arguments require a later,
        # explicit structured interpretation step.
        return (
            "goal",
            task,
            None,
        )

    @staticmethod
    def _normalize(
        text: str | None,
    ) -> str:
        if text is None:
            return ""

        normalized = str(
            text
        ).strip().lower()

        normalized = re.sub(
            r"\s+",
            " ",
            normalized,
        )

        normalized = normalized.strip(
            " \t\r\n.,!?;:"
        )

        return normalized

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
