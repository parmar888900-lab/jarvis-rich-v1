"""Startup recovery for uncertain external production operations."""

import logging
from collections.abc import Callable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.orchestration.production_operation_reconciliation import (
    ProductionOperationReconciliationService,
)
from backend.services.orchestration.production_operation_recovery import (
    ProductionOperationRecoveryService,
)

logger = logging.getLogger(__name__)


class ProductionOperationRecoveryRunner:
    """Recover and reconcile interrupted external side effects."""

    def __init__(
        self,
        *,
        recovery_service: ProductionOperationRecoveryService | None = None,
        reconciliation_service: (
            ProductionOperationReconciliationService | None
        ) = None,
    ) -> None:

        self.recovery_service = (
            recovery_service
            if recovery_service is not None
            else ProductionOperationRecoveryService()
        )

        self.reconciliation_service = (
            reconciliation_service
            if reconciliation_service is not None
            else ProductionOperationReconciliationService()
        )

    async def run(
        self,
        session: AsyncSession,
        *,
        stale_after_seconds: float,
    ) -> dict:
        """Recover stale operations and reconcile unresolved provider state.

        Recovery is intentionally best-effort. A provider outage must not
        prevent the Jarvis application from starting.
        """

        stale_records = (
            await self.recovery_service
            .find_stale_in_progress(
                session,
                stale_after_seconds=(
                    stale_after_seconds
                ),
            )
        )

        recovered_count = 0

        for record in stale_records:
            try:
                await (
                    self.recovery_service
                    .mark_reconciliation_required(
                        session,
                        record,
                        reason=(
                            "startup_stale_operation_"
                            "requires_reconciliation"
                        ),
                    )
                )

                recovered_count += 1

            except Exception:
                logger.exception(
                    "Failed to mark stale production "
                    "operation %s for reconciliation.",
                    getattr(
                        record,
                        "id",
                        "unknown",
                    ),
                )

                try:
                    await session.rollback()
                except Exception:
                    logger.exception(
                        "Failed to rollback operation "
                        "recovery transaction."
                    )

        unresolved = (
            await self.recovery_service
            .find_reconciliation_required(
                session
            )
        )

        completed_count = 0
        failed_count = 0
        error_count = 0

        for record in unresolved:
            try:
                result = (
                    await self.reconciliation_service
                    .reconcile(
                        session,
                        record,
                    )
                )

                if (
                    result.get("status")
                    == "completed"
                ):
                    completed_count += 1

                else:
                    failed_count += 1

            except Exception:
                error_count += 1

                logger.exception(
                    "Startup reconciliation failed for "
                    "production operation %s.",
                    getattr(
                        record,
                        "id",
                        "unknown",
                    ),
                )

                try:
                    await session.rollback()
                except Exception:
                    logger.exception(
                        "Failed to rollback startup "
                        "reconciliation transaction."
                    )

        return {
            "stale_found": len(
                stale_records
            ),
            "marked_for_reconciliation": (
                recovered_count
            ),
            "reconciliation_candidates": len(
                unresolved
            ),
            "reconciled_completed": (
                completed_count
            ),
            "reconciled_failed": (
                failed_count
            ),
            "reconciliation_errors": (
                error_count
            ),
        }
