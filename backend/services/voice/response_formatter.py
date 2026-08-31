"""Safe concise responses for Jarvis voice interactions."""

from __future__ import annotations

from typing import Any


class VoiceResponseFormatter:
    """Convert voice execution results into short spoken responses."""

    _TREND_KEYS = (
        "title",
        "topic",
        "name",
        "query",
        "trend",
    )

    _NESTED_TREND_KEYS = (
        "trend",
        "topic",
        "candidate",
        "source",
    )

    def format(self, result: Any) -> str:
        """Return a concise user-facing response."""

        status = getattr(
            result,
            "status",
            None,
        )

        if status == "confirmation_required":
            return (
                "This action requires confirmation "
                "before I can continue."
            )

        if status == "blocked":
            return (
                "I can't perform that action "
                "through voice control."
            )

        if status == "wake_only":
            return "Yes?"

        if status == "no_speech":
            return (
                "I didn't catch that. "
                "Please try again."
            )

        if status == "wake_not_detected":
            return ""

        if status != "completed":
            return (
                "I couldn't complete that request."
            )

        agent = getattr(
            result,
            "agent",
            None,
        )

        task = getattr(
            result,
            "task",
            None,
        )

        execution = getattr(
            result,
            "execution",
            None,
        )

        payload = getattr(
            execution,
            "result",
            None,
        )

        if (
            agent == "youtube"
            and task == "analyze_trends"
        ):
            return self._format_trend_analysis(
                payload
            )

        if (
            agent == "youtube"
            and task == "create_video"
        ):
            return (
                "The video has been created "
                "successfully."
            )

        if (
            agent == "youtube"
            and task == "upload_video"
        ):
            return (
                "The private video upload "
                "completed successfully."
            )

        if (
            agent == "goal"
            and task == "list_goals"
        ):
            return (
                "I finished checking your "
                "current goals."
            )

        if (
            agent == "goal"
            and task == "get_goal_status"
        ):
            return (
                "I finished checking the "
                "goal status."
            )

        if agent == "goal":
            return (
                "The goal operation completed "
                "successfully."
            )

        return (
            "The request completed successfully."
        )

    def _format_trend_analysis(
        self,
        payload: Any,
    ) -> str:
        if not isinstance(
            payload,
            dict,
        ):
            return (
                "Trend analysis completed "
                "successfully."
            )

        status = payload.get(
            "status"
        )

        if status == "no_trends_found":
            return (
                "Trend analysis is complete, "
                "but I couldn't find any "
                "viable trends."
            )

        if (
            status
            == "no_production_ready_topic"
        ):
            count = self._safe_count(
                payload.get(
                    "final_trend_count"
                )
            )

            if count is not None:
                return (
                    "Trend analysis is complete. "
                    f"I reviewed {count} "
                    "shortlisted topics, but none "
                    "passed the production gate."
                )

            return (
                "Trend analysis is complete, "
                "but no topic passed the "
                "production gate."
            )

        if status != "success":
            return (
                "I couldn't complete the "
                "trend analysis successfully."
            )

        count = self._safe_count(
            payload.get(
                "final_trend_count"
            )
        )

        title = self._extract_trend_title(
            payload.get(
                "best_trend"
            )
        )

        if (
            count is not None
            and title
        ):
            return (
                "Trend analysis complete. "
                f"I shortlisted {count} topics. "
                "The strongest candidate is "
                f"{title}."
            )

        if count is not None:
            return (
                "Trend analysis complete. "
                f"I shortlisted {count} "
                "production candidates."
            )

        if title:
            return (
                "Trend analysis complete. "
                "The strongest candidate is "
                f"{title}."
            )

        return (
            "Trend analysis completed "
            "successfully."
        )

    @classmethod
    def _extract_trend_title(
        cls,
        value: Any,
        *,
        depth: int = 0,
    ) -> str | None:
        if depth > 2:
            return None

        if isinstance(
            value,
            str,
        ):
            return cls._clean_text(
                value
            )

        if not isinstance(
            value,
            dict,
        ):
            return None

        for key in cls._TREND_KEYS:
            candidate = value.get(
                key
            )

            if isinstance(
                candidate,
                str,
            ):
                cleaned = cls._clean_text(
                    candidate
                )

                if cleaned:
                    return cleaned

        for key in cls._NESTED_TREND_KEYS:
            candidate = value.get(
                key
            )

            if candidate is value:
                continue

            title = cls._extract_trend_title(
                candidate,
                depth=depth + 1,
            )

            if title:
                return title

        return None

    @staticmethod
    def _clean_text(
        value: str,
    ) -> str | None:
        cleaned = " ".join(
            value.split()
        ).strip()

        if not cleaned:
            return None

        # Keep spoken responses bounded even if a
        # provider returns an unexpectedly long title.
        if len(cleaned) > 140:
            cleaned = (
                cleaned[:137].rstrip()
                + "..."
            )

        return cleaned

    @staticmethod
    def _safe_count(
        value: Any,
    ) -> int | None:
        if isinstance(
            value,
            bool,
        ):
            return None

        if isinstance(
            value,
            int,
        ) and value >= 0:
            return value

        return None
