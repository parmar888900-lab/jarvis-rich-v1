"""Tests for stale production-operation recovery."""

import asyncio
import os
import tempfile

from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import (
    async_sessionmaker,
    create_async_engine,
)

from backend.database import Base
from backend.services.orchestration.idempotency import (
    OperationType,
    build_idempotency_key,
)
from backend.services.orchestration.production_operation_service import (
    ProductionOperationService,
)
from backend.services.orchestration.production_operation_recovery import (
    ProductionOperationRecoveryService,
)


async def main():
    print("=" * 70)
    print(
        "PRODUCTION OPERATION "
        "RECOVERY TEST"
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

    service = ProductionOperationService()
    recovery = (
        ProductionOperationRecoveryService()
    )

    try:
        async with engine.begin() as conn:
            await conn.run_sync(
                Base.metadata.create_all
            )

        stale_key = build_idempotency_key(
            OperationType.UPLOAD_VIDEO,
            "stale-video",
        )

        fresh_key = build_idempotency_key(
            OperationType.UPLOAD_VIDEO,
            "fresh-video",
        )

        async with session_factory() as session:
            stale, created = await service.claim(
                session,
                idempotency_key=stale_key,
                operation_type=(
                    OperationType
                    .UPLOAD_VIDEO
                    .value
                ),
                resource_id="stale-video",
            )

            assert created is True

            stale.started_at = (
                datetime.utcnow()
                - timedelta(hours=2)
            )

            await session.commit()

        async with session_factory() as session:
            fresh, created = await service.claim(
                session,
                idempotency_key=fresh_key,
                operation_type=(
                    OperationType
                    .UPLOAD_VIDEO
                    .value
                ),
                resource_id="fresh-video",
            )

            assert created is True

        async with session_factory() as session:
            stale_records = (
                await recovery.find_stale_in_progress(
                    session,
                    stale_after_seconds=3600,
                )
            )

            assert len(stale_records) == 1
            assert (
                stale_records[0]
                .idempotency_key
                == stale_key
            )

            print(
                "PASS: stale in-progress "
                "operation is detected."
            )

            recovered = (
                await recovery
                .mark_reconciliation_required(
                    session,
                    stale_records[0],
                )
            )

            assert recovered.status == "failed"

            assert (
                recovered.error
                == (
                    "stale_in_progress_requires_"
                    "reconciliation"
                )
            )

            print(
                "PASS: stale operation is "
                "blocked from blind retry."
            )

        async with session_factory() as session:
            remaining = (
                await recovery.find_stale_in_progress(
                    session,
                    stale_after_seconds=3600,
                )
            )

            assert remaining == []

            fresh_record = (
                await service.get_by_key(
                    session,
                    fresh_key,
                )
            )

            assert fresh_record is not None
            assert (
                fresh_record.status
                == "in_progress"
            )

            print(
                "PASS: fresh operation "
                "is not recovered."
            )

        print()
        print("=" * 70)
        print(
            "ALL PRODUCTION OPERATION "
            "RECOVERY TESTS PASSED"
        )

    finally:
        await engine.dispose()

        try:
            os.remove(path)
        except PermissionError:
            pass


if __name__ == "__main__":
    asyncio.run(main())
