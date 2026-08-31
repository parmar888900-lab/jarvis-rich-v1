"""Startup production-operation recovery runner regression."""

import asyncio
import os
import tempfile
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import (
    async_sessionmaker,
    create_async_engine,
)

from backend.database import Base
from backend.models.production_operation import (
    ProductionOperationRecord,
)
from backend.services.orchestration.idempotency import (
    OperationType,
    build_idempotency_key,
)
from backend.services.orchestration.production_operation_recovery_runner import (
    ProductionOperationRecoveryRunner,
)
from backend.services.orchestration.production_operation_recovery import (
    ProductionOperationRecoveryService,
)


class FakeReconciliationService:

    def __init__(self):
        self.calls = []

    async def reconcile(
        self,
        session,
        record,
    ):
        self.calls.append(
            record.id
        )

        record.status = "completed"
        record.error = None
        record.retry_authorized = False
        record.completed_at = (
            datetime.now(
                timezone.utc
            ).replace(
                tzinfo=None
            )
        )

        await session.commit()
        await session.refresh(
            record
        )

        return {
            "status": "completed",
            "safe_to_retry": False,
            "record_id": record.id,
        }


class FailingReconciliationService:

    def __init__(self):
        self.calls = 0

    async def reconcile(
        self,
        session,
        record,
    ):
        self.calls += 1

        raise ConnectionError(
            "simulated provider outage"
        )


async def add_operation(
    session,
    *,
    resource_id,
    status,
    started_at,
):
    key = build_idempotency_key(
        OperationType.UPLOAD_VIDEO,
        resource_id,
    )

    record = ProductionOperationRecord(
        idempotency_key=key,
        operation_type=(
            OperationType.UPLOAD_VIDEO.value
        ),
        resource_id=resource_id,
        status=status,
        retry_authorized=False,
        started_at=started_at,
    )

    session.add(record)
    await session.commit()
    await session.refresh(record)

    return record


async def main():

    print("=" * 72)
    print(
        "PRODUCTION OPERATION STARTUP "
        "RECOVERY RUNNER TEST"
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

    try:

        async with engine.begin() as connection:
            await connection.run_sync(
                Base.metadata.create_all
            )

        now = datetime.now(
            timezone.utc
        ).replace(
            tzinfo=None
        )

        async with session_factory() as session:

            stale = await add_operation(
                session,
                resource_id=(
                    "youtube:startup-channel:"
                    "stale-artifact"
                ),
                status="in_progress",
                started_at=(
                    now
                    - timedelta(
                        hours=8
                    )
                ),
            )

            existing = await add_operation(
                session,
                resource_id=(
                    "youtube:startup-channel:"
                    "existing-uncertain-artifact"
                ),
                status=(
                    "reconciliation_required"
                ),
                started_at=(
                    now
                    - timedelta(
                        hours=2
                    )
                ),
            )

            fresh = await add_operation(
                session,
                resource_id=(
                    "youtube:startup-channel:"
                    "fresh-artifact"
                ),
                status="in_progress",
                started_at=(
                    now
                    - timedelta(
                        minutes=5
                    )
                ),
            )

            fake_reconciliation = (
                FakeReconciliationService()
            )

            runner = (
                ProductionOperationRecoveryRunner(
                    recovery_service=(
                        ProductionOperationRecoveryService()
                    ),
                    reconciliation_service=(
                        fake_reconciliation
                    ),
                )
            )

            summary = await runner.run(
                session,
                stale_after_seconds=(
                    6 * 60 * 60
                ),
            )

            assert (
                summary["stale_found"]
                == 1
            )

            assert (
                summary[
                    "marked_for_reconciliation"
                ]
                == 1
            )

            assert (
                summary[
                    "reconciliation_candidates"
                ]
                == 2
            )

            assert (
                summary[
                    "reconciled_completed"
                ]
                == 2
            )

            assert (
                summary[
                    "reconciliation_errors"
                ]
                == 0
            )

            await session.refresh(
                stale
            )

            await session.refresh(
                existing
            )

            await session.refresh(
                fresh
            )

            assert (
                stale.status
                == "completed"
            )

            assert (
                existing.status
                == "completed"
            )

            assert (
                fresh.status
                == "in_progress"
            )

        print(
            "PASS: stale IN_PROGRESS operation "
            "was recovered automatically."
        )

        print(
            "PASS: pre-existing "
            "RECONCILIATION_REQUIRED operation "
            "was discovered."
        )

        print(
            "PASS: all uncertain operations were "
            "reconciled before production startup."
        )

        print(
            "PASS: fresh operation was not "
            "incorrectly recovered."
        )

        # --------------------------------------------------
        # Provider/service outage must not abort recovery run.
        # --------------------------------------------------

        async with session_factory() as session:

            uncertain = await add_operation(
                session,
                resource_id=(
                    "youtube:startup-channel:"
                    "provider-outage-artifact"
                ),
                status=(
                    "reconciliation_required"
                ),
                started_at=now,
            )

            failing = (
                FailingReconciliationService()
            )

            runner = (
                ProductionOperationRecoveryRunner(
                    reconciliation_service=(
                        failing
                    )
                )
            )

            summary = await runner.run(
                session,
                stale_after_seconds=(
                    6 * 60 * 60
                ),
            )

            assert (
                summary[
                    "reconciliation_errors"
                ]
                == 1
            )

            await session.refresh(
                uncertain
            )

            assert (
                uncertain.status
                == "reconciliation_required"
            )

            assert (
                uncertain.retry_authorized
                is False
            )

        print(
            "PASS: reconciliation exception "
            "did not abort startup recovery."
        )

        print(
            "PASS: unresolved provider state "
            "remained retry-blocked."
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
