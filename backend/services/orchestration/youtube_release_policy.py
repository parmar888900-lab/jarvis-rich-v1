"""Fail-closed policy for releasing autonomous YouTube videos."""

from __future__ import annotations

from typing import Any


class YoutubeReleasePolicy:
    """
    Decide whether a private autonomous upload may be released.

    This class is deliberately side-effect free. It cannot upload,
    publish, schedule, or mutate a YouTube video.

    Publication is authorized only when every required release gate
    passes. Missing or malformed evidence therefore fails closed.
    """

    DEFAULT_MIN_PRODUCTION_SCORE = 70.0

    def __init__(
        self,
        *,
        enabled: bool = True,
        min_production_score: float = DEFAULT_MIN_PRODUCTION_SCORE,
        require_manual_approval: bool = True,
    ) -> None:
        if isinstance(min_production_score, bool):
            raise ValueError(
                "min_production_score must be numeric."
            )

        try:
            score = float(min_production_score)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "min_production_score must be numeric."
            ) from exc

        if not 0.0 <= score <= 100.0:
            raise ValueError(
                "min_production_score must be between 0 and 100."
            )

        self.enabled = enabled is True
        self.min_production_score = score
        self.require_manual_approval = (
            require_manual_approval is True
        )

    def evaluate(
        self,
        *,
        cycle_result: dict[str, Any] | None,
        manual_approved: bool = False,
    ) -> dict[str, Any]:
        """Return a structured fail-closed release decision."""

        reasons: list[str] = []

        if not self.enabled:
            reasons.append("release_disabled")

        result = (
            cycle_result
            if isinstance(cycle_result, dict)
            else {}
        )

        if result.get("status") != "completed":
            reasons.append(
                "production_cycle_not_completed"
            )

        trend = result.get("selected_trend")
        trend = trend if isinstance(trend, dict) else {}

        selection = trend.get("production_selection")
        selection = (
            selection
            if isinstance(selection, dict)
            else {}
        )

        if selection.get("eligible") is not True:
            reasons.append(
                "production_selection_not_eligible"
            )

        if selection.get("selected") is not True:
            reasons.append(
                "production_selection_not_selected"
            )

        production_score = self._number(
            selection.get("production_score")
        )

        if production_score is None:
            reasons.append(
                "production_score_unavailable"
            )
        elif production_score < self.min_production_score:
            reasons.append(
                "production_score_below_threshold"
            )

        upload = result.get("upload")
        upload = upload if isinstance(upload, dict) else {}

        if upload.get("status") != "completed":
            reasons.append("upload_not_completed")

        privacy_status = str(
            upload.get("privacy_status") or ""
        ).strip().lower()

        if privacy_status != "private":
            reasons.append(
                "video_not_private"
            )

        video_id = self._extract_video_id(upload)

        if not video_id:
            reasons.append(
                "youtube_video_id_unavailable"
            )

        if (
            self.require_manual_approval
            and manual_approved is not True
        ):
            reasons.append(
                "manual_approval_required"
            )

        authorized = not reasons

        return {
            "status": (
                "authorized"
                if authorized
                else "denied"
            ),
            "authorized": authorized,
            "reasons": reasons,
            "release_enabled": self.enabled,
            "require_manual_approval": (
                self.require_manual_approval
            ),
            "manual_approved": (
                manual_approved is True
            ),
            "min_production_score": round(
                self.min_production_score,
                2,
            ),
            "production_score": (
                round(production_score, 2)
                if production_score is not None
                else None
            ),
            "current_privacy_status": (
                privacy_status or None
            ),
            "video_id": video_id or None,
            "target_privacy_status": (
                "public"
                if authorized
                else None
            ),
        }

    @staticmethod
    def _extract_video_id(
        upload: dict[str, Any],
    ) -> str:
        """
        Extract provider video ID from the protected upload result.

        IdempotentOperationExecutor stores provider output under
        upload.result on successful execution.
        """

        operation = upload.get("upload")

        if not isinstance(operation, dict):
            return ""

        provider_result = operation.get("result")

        if not isinstance(provider_result, dict):
            return ""

        return str(
            provider_result.get("video_id") or ""
        ).strip()

    @staticmethod
    def _number(value: Any) -> float | None:
        if isinstance(value, bool):
            return None

        if isinstance(value, (int, float)):
            return float(value)

        return None

