"""Recovery logic for stale production operations."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.production_operation import (
    ProductionOperationRecord,
    ProductionOperationStatus,
)


class ProductionOperationRecoveryService:
    """Recover stale side-effect operation records safely."""

    @staticmethod
    def _utc_now() -> datetime:
        return datetime.now(
            timezone.utc
        ).replace(
            tzinfo=None
        )

    async def find_stale_in_progress(
        self,
        session: AsyncSession,
        *,
        stale_after_seconds: float,
    ) -> list[ProductionOperationRecord]:
        if stale_after_seconds < 0:
            raise ValueError(
                "stale_after_seconds cannot be negative."
            )

        cutoff = (
            self._utc_now()
            - timedelta(
                seconds=stale_after_seconds
            )
        )

        statement = (
            select(
                ProductionOperationRecord
            )
            .where(
                ProductionOperationRecord.status
                == ProductionOperationStatus
                .IN_PROGRESS
                .value
            )
            .where(
                ProductionOperationRecord.started_at
                <= cutoff
            )
            .order_by(
                ProductionOperationRecord.started_at
                .asc()
            )
        )

        result = await session.execute(
            statement
        )

        return list(
            result.scalars().all()
        )

    async def mark_reconciliation_required(
        self,
        session: AsyncSession,
        record: ProductionOperationRecord,
        *,
        reason: str = (
            "stale_in_progress_requires_reconciliation"
        ),
    ) -> ProductionOperationRecord:
        if (
            record.status
            != ProductionOperationStatus
            .IN_PROGRESS
            .value
        ):
            raise ValueError(
                "Only in-progress operations "
                "can require reconciliation."
            )

        record.status = (
            ProductionOperationStatus
            .FAILED
            .value
        )

        record.error = reason
        record.completed_at = (
            self._utc_now()
        )

        await session.commit()
        await session.refresh(record)

        return record
