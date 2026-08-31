"""Persistent YouTube reconciliation integration regression."""

import asyncio
import json
import os
import tempfile

from sqlalchemy.ext.asyncio import (
    async_sessionmaker,
    create_async_engine,
)

from backend.database import Base
from backend.services.orchestration.idempotency import (
    OperationType,
    build_idempotency_key,
)
from backend.services.orchestration.production_operation_reconciliation import (
    ProductionOperationReconciliationService,
)
from backend.services.orchestration.production_operation_recovery import (
    ProductionOperationRecoveryService,
)
from backend.services.orchestration.production_operation_service import (
    ProductionOperationService,
)
from backend.services.providers.youtube_publisher import (
    build_youtube_operation_tag,
)
from backend.services.providers.youtube_upload_reconciler import (
    YoutubeUploadReconciler,
)


class FakeYoutubePublisher:

    def __init__(self):
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

        return {
            "channel_id": (
                "integration-channel"
            ),
            "video_id": (
                "recovered-youtube-video-123"
            ),
            "title": (
                "Recovered YouTube Upload"
            ),
            "operation_tag": operation_tag,
        }


async def main():

    print("=" * 72)
    print(
        "YOUTUBE OPERATION RECONCILIATION "
        "INTEGRATION TEST"
    )
    print("=" * 72)

    fd, database_path = tempfile.mkstemp(
        suffix=".db"
    )

    os.close(fd)

    engine = create_async_engine(
        (
            "sqlite+aiosqlite:///"
            f"{database_path}"
        ),
        connect_args={
            "timeout": 30,
        },
    )

    session_factory = (
        async_sessionmaker(
            engine,
            expire_on_commit=False,
        )
    )

    operation_service = (
        ProductionOperationService()
    )

    recovery_service = (
        ProductionOperationRecoveryService()
    )

    publisher = FakeYoutubePublisher()

    youtube_reconciler = (
        YoutubeUploadReconciler(
            publisher
        )
    )

    reconciliation_service = (
        ProductionOperationReconciliationService(
            operation_service=(
                operation_service
            ),
            youtube_reconciler=(
                youtube_reconciler
            ),
        )
    )

    resource_id = (
        "youtube:integration-channel:"
        "artifact-sha256-test"
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

    try:

        async with engine.begin() as connection:
            await connection.run_sync(
                Base.metadata.create_all
            )

        async with session_factory() as session:

            record, created = (
                await operation_service.claim(
                    session,
                    idempotency_key=key,
                    operation_type=(
                        OperationType
                        .UPLOAD_VIDEO
                        .value
                    ),
                    resource_id=resource_id,
                )
            )

            assert created is True

            record = (
                await recovery_service
                .mark_reconciliation_required(
                    session,
                    record,
                    reason=(
                        "simulated_lost_provider_response"
                    ),
                )
            )

            assert (
                record.status
                == "reconciliation_required"
            )

            # Critical point:
            # no reconciler argument is supplied.
            # The service must route the YouTube
            # operation automatically.
            result = (
                await reconciliation_service
                .reconcile(
                    session,
                    record,
                )
            )

            assert (
                result["status"]
                == "completed"
            )

            assert (
                result["safe_to_retry"]
                is False
            )

            assert (
                result["external_id"]
                == (
                    "recovered-youtube-video-123"
                )
            )

            assert (
                record.status
                == "completed"
            )

            assert (
                record.retry_authorized
                is False
            )

            assert (
                record.error
                is None
            )

            stored_result = json.loads(
                record.result
            )

            assert (
                stored_result["reconciled"]
                is True
            )

            assert (
                stored_result["external_id"]
                == (
                    "recovered-youtube-video-123"
                )
            )

            assert len(
                publisher.calls
            ) == 1

            assert (
                publisher.calls[0][
                    "operation_tag"
                ]
                == expected_tag
            )

        print(
            "PASS: persistent uncertain "
            "YouTube record reconciled automatically."
        )

        print(
            "PASS: real YoutubeUploadReconciler "
            "confirmed exact provider marker."
        )

        print(
            "PASS: RECONCILIATION_REQUIRED "
            "became COMPLETED."
        )

        print(
            "PASS: recovered provider video ID "
            "was persisted."
        )

        print(
            "PASS: retry remained unauthorized."
        )

    finally:

        await engine.dispose()

        try:
            os.remove(
                database_path
            )

        except PermissionError:
            pass

    print("=" * 72)


if __name__ == "__main__":
    asyncio.run(main())
