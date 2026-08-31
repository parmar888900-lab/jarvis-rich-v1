"""YouTube reconciliation for uncertain video uploads."""

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
    build_youtube_operation_tag,
)


class YoutubeUploadReconciler:
    """Reconcile uncertain uploads using provider metadata."""

    def __init__(
        self,
        publisher: YoutubePublisher,
        *,
        max_items: int = 200,
    ) -> None:
        self.publisher = publisher
        self.max_items = max_items

    @staticmethod
    def _resource_channel_id(
        resource_id: str,
    ) -> str | None:

        parts = resource_id.split(
            ":",
            2,
        )

        if (
            len(parts) != 3
            or parts[0] != "youtube"
        ):
            return None

        channel_id = parts[1].strip()

        return (
            channel_id
            if channel_id
            else None
        )

    async def reconcile(
        self,
        *,
        operation_type: str,
        resource_id: str,
        idempotency_key: str,
    ) -> ReconciliationResult:

        if (
            operation_type
            != OperationType.UPLOAD_VIDEO.value
        ):
            return ReconciliationResult(
                status=(
                    ReconciliationStatus.UNKNOWN
                ),
                detail=(
                    "unsupported_youtube_operation:"
                    f"{operation_type}"
                ),
            )

        expected_channel_id = (
            self._resource_channel_id(
                resource_id
            )
        )

        if expected_channel_id is None:
            return ReconciliationResult(
                status=(
                    ReconciliationStatus.UNKNOWN
                ),
                detail=(
                    "invalid_youtube_resource_id"
                ),
            )

        operation_tag = (
            build_youtube_operation_tag(
                idempotency_key
            )
        )

        try:
            found = await asyncio.to_thread(
                self.publisher
                .find_uploaded_video_by_operation_tag,
                operation_tag,
                max_items=self.max_items,
            )

        except Exception as exc:
            return ReconciliationResult(
                status=(
                    ReconciliationStatus.UNKNOWN
                ),
                detail=(
                    "youtube_reconciliation_error:"
                    f"{exc}"
                ),
            )

        if found is None:
            # Absence from a bounded recent-upload scan
            # cannot safely authorize another upload.
            return ReconciliationResult(
                status=(
                    ReconciliationStatus.UNKNOWN
                ),
                detail=(
                    "youtube_operation_marker_not_found"
                ),
            )

        actual_channel_id = str(
            found.get(
                "channel_id",
                "",
            )
        ).strip()

        if (
            actual_channel_id
            != expected_channel_id
        ):
            return ReconciliationResult(
                status=(
                    ReconciliationStatus.UNKNOWN
                ),
                detail=(
                    "youtube_reconciliation_channel_mismatch"
                ),
            )

        video_id = str(
            found.get(
                "video_id",
                "",
            )
        ).strip()

        if not video_id:
            return ReconciliationResult(
                status=(
                    ReconciliationStatus.UNKNOWN
                ),
                detail=(
                    "youtube_reconciliation_missing_video_id"
                ),
            )

        return ReconciliationResult(
            status=(
                ReconciliationStatus
                .CONFIRMED_COMPLETED
            ),
            external_id=video_id,
            detail=(
                "youtube_operation_marker_confirmed"
            ),
        )
