"""Regression tests for YouTube publication reconciliation."""

import asyncio

from backend.services.orchestration.idempotency import (
    OperationType,
)
from backend.services.orchestration.operation_reconciliation import (
    ReconciliationStatus,
)
from backend.services.providers.youtube_publish_reconciler import (
    YoutubePublishReconciler,
)


class FakePublisher:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.calls = []

    def get_video_status(self, video_id):
        self.calls.append(video_id)

        if self.error is not None:
            raise self.error

        return self.result


async def reconcile(result=None, error=None):
    publisher = FakePublisher(
        result=result,
        error=error,
    )

    reconciler = YoutubePublishReconciler(
        publisher
    )

    output = await reconciler.reconcile(
        operation_type=(
            OperationType.PUBLISH_VIDEO.value
        ),
        resource_id=(
            "youtube-publish:"
            "channel-1:"
            "video-1"
        ),
        idempotency_key="publish-key",
    )

    return output, publisher


async def main():
    output, _ = await reconcile(
        {
            "status": "found",
            "video_id": "video-1",
            "channel_id": "channel-1",
            "authorized_channel_id": "channel-1",
            "privacy_status": "public",
        }
    )

    assert (
        output.status
        == ReconciliationStatus.CONFIRMED_COMPLETED
    )
    assert output.external_id == "video-1"

    print(
        "PASS: PUBLIC provider state confirms "
        "completed publication."
    )

    for privacy in (
        "private",
        "unlisted",
    ):
        output, _ = await reconcile(
            {
                "status": "found",
                "video_id": "video-1",
                "channel_id": "channel-1",
                "authorized_channel_id": "channel-1",
                "privacy_status": privacy,
            }
        )

        assert (
            output.status
            == ReconciliationStatus.CONFIRMED_NOT_FOUND
        )

    print(
        "PASS: non-public provider state safely "
        "authorizes publication retry."
    )

    output, _ = await reconcile(
        {
            "status": "found",
            "video_id": "video-1",
            "channel_id": "wrong-channel",
            "authorized_channel_id": "channel-1",
            "privacy_status": "public",
        }
    )

    assert (
        output.status
        == ReconciliationStatus.UNKNOWN
    )

    print(
        "PASS: channel mismatch fails closed."
    )

    output, _ = await reconcile(
        {
            "status": "not_found",
            "video_id": "video-1",
            "authorized_channel_id": "channel-1",
        }
    )

    assert (
        output.status
        == ReconciliationStatus.UNKNOWN
    )

    print(
        "PASS: missing video does not authorize "
        "automatic retry."
    )

    output, _ = await reconcile(
        error=RuntimeError(
            "provider unavailable"
        )
    )

    assert (
        output.status
        == ReconciliationStatus.UNKNOWN
    )

    print(
        "PASS: reconciliation read failure "
        "fails closed."
    )

    publisher = FakePublisher(
        result={}
    )

    reconciler = YoutubePublishReconciler(
        publisher
    )

    output = await reconciler.reconcile(
        operation_type="upload_video",
        resource_id=(
            "youtube-publish:"
            "channel-1:"
            "video-1"
        ),
        idempotency_key="key",
    )

    assert (
        output.status
        == ReconciliationStatus.UNKNOWN
    )
    assert not publisher.calls

    print(
        "PASS: reconciler rejects unsupported "
        "operation types."
    )

    print(
        "PASS: YouTube publish reconciliation "
        "regression suite complete."
    )


if __name__ == "__main__":
    asyncio.run(main())
