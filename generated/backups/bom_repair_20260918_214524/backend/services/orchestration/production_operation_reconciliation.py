"""Reconcile stale production operations with external providers."""

import json

from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.production_operation import (
    ProductionOperationRecord,
    ProductionOperationStatus,
)
from backend.services.orchestration.operation_reconciliation import (
    OperationReconciler,
    ReconciliationStatus,
)
from backend.services.orchestration.production_operation_service import (
    ProductionOperationService,
)
from backend.services.providers.youtube_publisher import (
    YoutubePublisher,
)
from backend.services.providers.youtube_upload_reconciler import (
    YoutubeUploadReconciler,
)
from backend.services.providers.youtube_publish_reconciler import (
    YoutubePublishReconciler,
)


class ProductionOperationReconciliationService:
    """Resolve uncertain production operations using provider evidence."""

    def __init__(
        self,
        *,
        operation_service: ProductionOperationService | None = None,
        youtube_reconciler: OperationReconciler | None = None,
        youtube_publish_reconciler: OperationReconciler | None = None,
    ) -> None:
        self.operation_service = (
            operation_service
            if operation_service is not None
            else ProductionOperationService()
        )

        self.youtube_reconciler = (
            youtube_reconciler
            if youtube_reconciler is not None
            else YoutubeUploadReconciler(
                YoutubePublisher()
            )
        )

        self.youtube_publish_reconciler = (
            youtube_publish_reconciler
            if youtube_publish_reconciler is not None
            else YoutubePublishReconciler(
                YoutubePublisher()
            )
        )

    async def reconcile(
        self,
        session: AsyncSession,
        record: ProductionOperationRecord,
        reconciler: OperationReconciler | None = None,
    ) -> dict:
        """Reconcile one explicitly uncertain operation."""

        if (
            record.status
            != ProductionOperationStatus
            .RECONCILIATION_REQUIRED
            .value
        ):
            raise ValueError(
                "Only reconciliation-required operations "
                "can be reconciled."
            )

        selected_reconciler = reconciler

        if selected_reconciler is None:
            if (
                record.operation_type
                == "upload_video"
                and record.resource_id.startswith(
                    "youtube:"
                )
            ):
                selected_reconciler = (
                    self.youtube_reconciler
                )

            elif (
                record.operation_type
                == "publish_video"
                and record.resource_id.startswith(
                    "youtube-publish:"
                )
            ):
                selected_reconciler = (
                    self.youtube_publish_reconciler
                )

            else:
                raise ValueError(
                    "No automatic reconciler is "
                    "registered for operation "
                    f"{record.operation_type!r} "
                    f"resource {record.resource_id!r}."
                )

        reconciliation = (
            await selected_reconciler.reconcile(
            operation_type=record.operation_type,
            resource_id=record.resource_id,
            idempotency_key=record.idempotency_key,
            )
        )

        if (
            reconciliation.status
            == ReconciliationStatus
            .CONFIRMED_COMPLETED
        ):
            completed = (
                await self.operation_service.complete_reconciled(
                    session,
                    record,
                    result={
                        "reconciled": True,
                        "external_id": (
                            reconciliation.external_id
                        ),
                        "detail": (
                            reconciliation.detail
                        ),
                    },
                )
            )

            return {
                "status": "completed",
                "safe_to_retry": False,
                "record_id": completed.id,
                "external_id": (
                    reconciliation.external_id
                ),
            }

        if (
            reconciliation.status
            == ReconciliationStatus
            .CONFIRMED_NOT_FOUND
        ):
            failed = (
                await self.operation_service.fail_reconciled(
                    session,
                    record,
                    error=(
                        "reconciliation_confirmed_not_found"
                    ),
                    retry_authorized=True,
                )
            )

            return {
                "status": "failed",
                "safe_to_retry": True,
                "record_id": failed.id,
            }

        failed = (
            await self.operation_service.fail_reconciled(
                session,
                record,
                error=(
                    "reconciliation_unknown:"
                    + (
                        reconciliation.detail
                        or "provider_state_uncertain"
                    )
                ),
                retry_authorized=False,
            )
        )

        return {
            "status": "failed",
            "safe_to_retry": False,
            "record_id": failed.id,
        }
