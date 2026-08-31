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


class ProductionOperationReconciliationService:
    """Resolve uncertain production operations using provider evidence."""

    def __init__(
        self,
        *,
        operation_service: ProductionOperationService | None = None,
    ) -> None:
        self.operation_service = (
            operation_service
            if operation_service is not None
            else ProductionOperationService()
        )

    async def reconcile(
        self,
        session: AsyncSession,
        record: ProductionOperationRecord,
        reconciler: OperationReconciler,
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

        reconciliation = await reconciler.reconcile(
            operation_type=record.operation_type,
            resource_id=record.resource_id,
            idempotency_key=record.idempotency_key,
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
