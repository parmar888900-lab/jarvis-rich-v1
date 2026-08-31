"""YouTube upload reconciliation regression."""

import asyncio

from backend.services.orchestration.idempotency import (
    OperationType,
    build_idempotency_key,
)
from backend.services.orchestration.operation_reconciliation import (
    ReconciliationStatus,
)
from backend.services.providers.youtube_publisher import (
    build_youtube_operation_tag,
)
from backend.services.providers.youtube_upload_reconciler import (
    YoutubeUploadReconciler,
)


class FakePublisher:

    def __init__(
        self,
        *,
        result=None,
        error=None,
    ):
        self.result = result
        self.error = error
        self.calls = []

    def find_uploaded_video_by_operation_tag(
        self,
        operation_tag,
        *,
        max_items=200,
    ):
        self.calls.append(
            {
                "operation_tag": operation_tag,
                "max_items": max_items,
            }
        )

        if self.error is not None:
            raise self.error

        return self.result


async def main():

    print("=" * 72)
    print(
        "YOUTUBE UPLOAD RECONCILER TEST"
    )
    print("=" * 72)

    resource_id = (
        "youtube:test-channel-123:"
        "0123456789abcdef"
    )

    key = build_idempotency_key(
        OperationType.UPLOAD_VIDEO,
        resource_id,
    )

    expected_tag = (
        build_youtube_operation_tag(
            key
        )
    )

    # --------------------------------------------------
    # Exact marker + correct channel
    # --------------------------------------------------

    publisher = FakePublisher(
        result={
            "channel_id": (
                "test-channel-123"
            ),
            "video_id": (
                "confirmed-video-123"
            ),
            "title": (
                "Recovered Short"
            ),
            "operation_tag": (
                expected_tag
            ),
        }
    )

    reconciler = YoutubeUploadReconciler(
        publisher
    )

    result = await reconciler.reconcile(
        operation_type=(
            OperationType.UPLOAD_VIDEO.value
        ),
        resource_id=resource_id,
        idempotency_key=key,
    )

    assert (
        result.status
        == ReconciliationStatus
        .CONFIRMED_COMPLETED
    )

    assert (
        result.external_id
        == "confirmed-video-123"
    )

    assert (
        publisher.calls[0][
            "operation_tag"
        ]
        == expected_tag
    )

    print(
        "PASS: exact provider marker "
        "confirms completion."
    )

    # --------------------------------------------------
    # Marker absent
    # --------------------------------------------------

    publisher = FakePublisher(
        result=None
    )

    reconciler = YoutubeUploadReconciler(
        publisher
    )

    result = await reconciler.reconcile(
        operation_type=(
            OperationType.UPLOAD_VIDEO.value
        ),
        resource_id=resource_id,
        idempotency_key=key,
    )

    assert (
        result.status
        == ReconciliationStatus.UNKNOWN
    )

    assert (
        result.safe_to_retry
        is False
    )

    print(
        "PASS: absent marker stays UNKNOWN; "
        "retry remains blocked."
    )

    # --------------------------------------------------
    # Provider query error
    # --------------------------------------------------

    publisher = FakePublisher(
        error=ConnectionError(
            "simulated provider failure"
        )
    )

    reconciler = YoutubeUploadReconciler(
        publisher
    )

    result = await reconciler.reconcile(
        operation_type=(
            OperationType.UPLOAD_VIDEO.value
        ),
        resource_id=resource_id,
        idempotency_key=key,
    )

    assert (
        result.status
        == ReconciliationStatus.UNKNOWN
    )

    assert (
        result.safe_to_retry
        is False
    )

    print(
        "PASS: reconciliation query error "
        "fails closed."
    )

    # --------------------------------------------------
    # Marker belongs to wrong channel
    # --------------------------------------------------

    publisher = FakePublisher(
        result={
            "channel_id": (
                "wrong-channel"
            ),
            "video_id": (
                "wrong-video"
            ),
            "operation_tag": (
                expected_tag
            ),
        }
    )

    reconciler = YoutubeUploadReconciler(
        publisher
    )

    result = await reconciler.reconcile(
        operation_type=(
            OperationType.UPLOAD_VIDEO.value
        ),
        resource_id=resource_id,
        idempotency_key=key,
    )

    assert (
        result.status
        == ReconciliationStatus.UNKNOWN
    )

    print(
        "PASS: channel mismatch cannot "
        "confirm completion."
    )

    print("=" * 72)


if __name__ == "__main__":
    asyncio.run(main())
