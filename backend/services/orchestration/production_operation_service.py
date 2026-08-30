"""Persistence service for idempotent production operations."""

import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.production_operation import (
    ProductionOperationRecord,
    ProductionOperationStatus,
)


class ProductionOperationService:
    """Manage persistent side-effecting production operations."""

    @staticmethod
    def _utc_now() -> datetime:
        """Return naive UTC for SQLite DateTime consistency."""

        return datetime.now(
            timezone.utc
        ).replace(
            tzinfo=None
        )

    async def get_by_key(
        self,
        session: AsyncSession,
        idempotency_key: str,
    ) -> ProductionOperationRecord | None:
        """Return an operation by idempotency key."""

        statement = select(
            ProductionOperationRecord
        ).where(
            ProductionOperationRecord.idempotency_key
            == idempotency_key
        )

        result = await session.execute(
            statement
        )

        return result.scalar_one_or_none()

    async def claim(
        self,
        session: AsyncSession,
        *,
        idempotency_key: str,
        operation_type: str,
        resource_id: str,
    ) -> tuple[
        ProductionOperationRecord,
        bool,
    ]:
        """Atomically claim an operation.

        Returns:
            (record, True) when this caller created the claim.
            (record, False) when the operation already existed.
        """

        record = ProductionOperationRecord(
            idempotency_key=idempotency_key,
            operation_type=operation_type,
            resource_id=resource_id,
            status=(
                ProductionOperationStatus
                .IN_PROGRESS
                .value
            ),
            started_at=self._utc_now(),
        )

        session.add(record)

        try:
            await session.commit()

        except IntegrityError:
            await session.rollback()

            existing = await self.get_by_key(
                session,
                idempotency_key,
            )

            if existing is None:
                raise

            return existing, False

        await session.refresh(record)

        return record, True

    async def complete(
        self,
        session: AsyncSession,
        record: ProductionOperationRecord,
        *,
        result: dict | None = None,
    ) -> ProductionOperationRecord:
        """Mark an in-progress operation completed."""

        if (
            record.status
            != ProductionOperationStatus
            .IN_PROGRESS
            .value
        ):
            raise ValueError(
                "Only an in-progress operation "
                "can be completed."
            )

        record.status = (
            ProductionOperationStatus
            .COMPLETED
            .value
        )

        record.result = (
            json.dumps(result)
            if result is not None
            else None
        )

        record.error = None
        record.completed_at = self._utc_now()

        await session.commit()
        await session.refresh(record)

        return record

    async def fail(
        self,
        session: AsyncSession,
        record: ProductionOperationRecord,
        *,
        error: str,
    ) -> ProductionOperationRecord:
        """Mark an in-progress operation failed."""

        if (
            record.status
            != ProductionOperationStatus
            .IN_PROGRESS
            .value
        ):
            raise ValueError(
                "Only an in-progress operation "
                "can be failed."
            )

        record.status = (
            ProductionOperationStatus
            .FAILED
            .value
        )

        record.error = error
        record.completed_at = self._utc_now()

        await session.commit()
        await session.refresh(record)

        return record

