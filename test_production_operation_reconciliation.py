"""Database lifecycle tests for production operation reconciliation."""

import asyncio
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
from backend.services.orchestration.operation_reconciliation import (
    ReconciliationResult,
    ReconciliationStatus,
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


class FakeReconciler:
    def __init__(
        self,
        result: ReconciliationResult,
    ) -> None:
        self.result = result
        self.calls = 0

    async def reconcile(
        self,
        *,
        operation_type: str,
        resource_id: str,
        idempotency_key: str,
    ) -> ReconciliationResult:
        self.calls += 1
        return self.result


async def create_operation(
    service,
    session,
    resource_id,
):
    key = build_idempotency_key(
        OperationType.UPLOAD_VIDEO,
        resource_id,
    )

    record, created = await service.claim(
        session,
        idempotency_key=key,
        operation_type=(
            OperationType.UPLOAD_VIDEO.value
        ),
        resource_id=resource_id,
    )

    assert created is True

    return record


async def main():
    print("=" * 70)
    print(
        "PRODUCTION OPERATION "
        "RECONCILIATION TEST"
    )
    print()

    fd, path = tempfile.mkstemp(
        suffix=".db"
    )
    os.close(fd)

    engine = create_async_engine(
        f"sqlite+aiosqlite:///{path}",
        connect_args={
            "timeout": 30,
        },
    )

    session_factory = async_sessionmaker(
        engine,
        expire_on_commit=False,
    )

    operation_service = (
        ProductionOperationService()
    )

    reconciliation_service = (
        ProductionOperationReconciliationService(
            operation_service=operation_service,
        )
    )

    recovery_service = (
        ProductionOperationRecoveryService()
    )

    try:
        async with engine.begin() as conn:
            await conn.run_sync(
                Base.metadata.create_all
            )

        # Case 1:
        # Provider confirms the side effect happened.

        async with session_factory() as session:
            record = await create_operation(
                operation_service,
                session,
                "confirmed-video",
            )

            record = (
                await recovery_service
                .mark_reconciliation_required(
                    session,
                    record,
                )
            )

            assert (
                record.status
                == "reconciliation_required"
            )

            reconciler = FakeReconciler(
                ReconciliationResult(
                    status=(
                        ReconciliationStatus
                        .CONFIRMED_COMPLETED
                    ),
                    external_id="youtube-123",
                )
            )

            result = (
                await reconciliation_service
                .reconcile(
                    session,
                    record,
                    reconciler,
                )
            )

            assert result["status"] == "completed"
            assert result["safe_to_retry"] is False
            assert (
                result["external_id"]
                == "youtube-123"
            )
            assert record.status == "completed"
            assert reconciler.calls == 1

            print(
                "PASS: provider-confirmed "
                "completion becomes COMPLETED."
            )

        # Case 2:
        # Provider proves the side effect did not happen.

        async with session_factory() as session:
            record = await create_operation(
                operation_service,
                session,
                "missing-video",
            )

            record = (
                await recovery_service
                .mark_reconciliation_required(
                    session,
                    record,
                )
            )

            assert (
                record.status
                == "reconciliation_required"
            )

            reconciler = FakeReconciler(
                ReconciliationResult(
                    status=(
                        ReconciliationStatus
                        .CONFIRMED_NOT_FOUND
                    ),
                )
            )

            result = (
                await reconciliation_service
                .reconcile(
                    session,
                    record,
                    reconciler,
                )
            )

            assert result["status"] == "failed"
            assert result["safe_to_retry"] is True
            assert record.status == "failed"
            assert record.retry_authorized is True

            assert (
                record.error
                == (
                    "reconciliation_"
                    "confirmed_not_found"
                )
            )

            print(
                "PASS: provider-confirmed "
                "absence authorizes retry."
            )

        # Case 3:
        # Provider cannot determine what happened.

        async with session_factory() as session:
            record = await create_operation(
                operation_service,
                session,
                "unknown-video",
            )

            record = (
                await recovery_service
                .mark_reconciliation_required(
                    session,
                    record,
                )
            )

            assert (
                record.status
                == "reconciliation_required"
            )

            reconciler = FakeReconciler(
                ReconciliationResult(
                    status=(
                        ReconciliationStatus
                        .UNKNOWN
                    ),
                    detail=(
                        "provider unavailable"
                    ),
                )
            )

            result = (
                await reconciliation_service
                .reconcile(
                    session,
                    record,
                    reconciler,
                )
            )

            assert result["status"] == "failed"
            assert result["safe_to_retry"] is False
            assert record.status == "failed"
            assert record.retry_authorized is False

            assert record.error.startswith(
                "reconciliation_unknown:"
            )

            print(
                "PASS: uncertain provider "
                "state fails closed."
            )

        print()
        print("=" * 70)
        print(
            "ALL PRODUCTION OPERATION "
            "RECONCILIATION TESTS PASSED"
        )

    finally:
        await engine.dispose()

        try:
            os.remove(path)
        except PermissionError:
            pass


if __name__ == "__main__":
    asyncio.run(main())
