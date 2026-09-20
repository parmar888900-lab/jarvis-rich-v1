"""YouTube reconciliation for uncertain privacy publication."""

import asyncio

from backend.services.orchestration.idempotency import (
    OperationType,
)
from backend.services.orchestration.operation_reconciliation import (
    ReconciliationResult,
    ReconciliationStatus,
)
from backend.services.providers.youtube_publisher import (
    YoutubePublisher,
)


class YoutubePublishReconciler:
    """Reconcile an uncertain private-to-public transition."""

    def __init__(
        self,
        publisher: YoutubePublisher,
    ) -> None:
        self.publisher = publisher

    @staticmethod
    def _resource_identity(
        resource_id: str,
    ) -> tuple[str, str] | None:
        parts = resource_id.split(
            ":",
            2,
        )

        if (
            len(parts) != 3
            or parts[0] != "youtube-publish"
        ):
            return None

        channel_id = parts[1].strip()
        video_id = parts[2].strip()

        if not channel_id or not video_id:
            return None

        return (
            channel_id,
            video_id,
        )

    async def reconcile(
        self,
        *,
        operation_type: str,
        resource_id: str,
        idempotency_key: str,
    ) -> ReconciliationResult:
        del idempotency_key

        if (
            operation_type
            != OperationType.PUBLISH_VIDEO.value
        ):
            return ReconciliationResult(
                status=ReconciliationStatus.UNKNOWN,
                detail=(
                    "unsupported_youtube_publish_operation:"
                    f"{operation_type}"
                ),
            )

        identity = self._resource_identity(
            resource_id
        )

        if identity is None:
            return ReconciliationResult(
                status=ReconciliationStatus.UNKNOWN,
                detail="invalid_youtube_publish_resource_id",
            )

        expected_channel_id, video_id = identity

        try:
            current = await asyncio.to_thread(
                self.publisher.get_video_status,
                video_id,
            )

        except Exception as exc:
            return ReconciliationResult(
                status=ReconciliationStatus.UNKNOWN,
                detail=(
                    "youtube_publish_reconciliation_error:"
                    f"{exc}"
                ),
            )

        if current.get("status") != "found":
            # A missing provider object is not sufficient
            # evidence for retrying publication automatically.
            return ReconciliationResult(
                status=ReconciliationStatus.UNKNOWN,
                detail=(
                    "youtube_publish_video_not_confirmed"
                ),
            )

        actual_channel_id = str(
            current.get(
                "channel_id",
                "",
            )
        ).strip()

        authorized_channel_id = str(
            current.get(
                "authorized_channel_id",
                "",
            )
        ).strip()

        if (
            actual_channel_id != expected_channel_id
            or authorized_channel_id != expected_channel_id
        ):
            return ReconciliationResult(
                status=ReconciliationStatus.UNKNOWN,
                detail=(
                    "youtube_publish_channel_mismatch"
                ),
            )

        privacy = str(
            current.get(
                "privacy_status",
                "",
            )
        ).strip().lower()

        if privacy == "public":
            return ReconciliationResult(
                status=(
                    ReconciliationStatus
                    .CONFIRMED_COMPLETED
                ),
                external_id=video_id,
                detail=(
                    "youtube_publication_confirmed"
                ),
            )

        if privacy in {
            "private",
            "unlisted",
        }:
            # Exact provider state proves the requested
            # transition to PUBLIC did not complete.
            return ReconciliationResult(
                status=(
                    ReconciliationStatus
                    .CONFIRMED_NOT_FOUND
                ),
                external_id=video_id,
                detail=(
                    "youtube_publication_not_applied"
                ),
            )

        return ReconciliationResult(
            status=ReconciliationStatus.UNKNOWN,
            detail=(
                "youtube_publish_privacy_state_unknown"
            ),
        )
