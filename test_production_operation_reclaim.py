"""Tests for atomic failed-operation reclaim."""

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
from backend.services.orchestration.production_operation_service import (
    ProductionOperationService,
)


async def main():
    print("=" * 70)
    print("PRODUCTION OPERATION RECLAIM TEST")
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

    try:
        async with engine.begin() as conn:
            await conn.run_sync(
                Base.metadata.create_all
            )

        authorized_key = build_idempotency_key(
            OperationType.UPLOAD_VIDEO,
            "authorized-retry-video",
        )

        async with session_factory() as session:
            record, created = await service.claim(
                session,
                idempotency_key=authorized_key,
                operation_type=(
                    OperationType
                    .UPLOAD_VIDEO
                    .value
                ),
                resource_id="authorized-retry-video",
            )

            assert created is True

            record = await service.fail(
                session,
                record,
                error="confirmed_not_found",
            )

            record.retry_authorized = True

            await session.commit()
            await session.refresh(record)

            assert record.status == "failed"
            assert record.retry_authorized is True

        async def reclaim_once():
            async with session_factory() as session:
                return await service.reclaim_failed(
                    session,
                    idempotency_key=authorized_key,
                )

        first, second = await asyncio.gather(
            reclaim_once(),
            reclaim_once(),
        )

        results = [first, second]

        winners = [
            item
            for item in results
            if item[1] is True
        ]

        losers = [
            item
            for item in results
            if item[1] is False
        ]

        assert len(winners) == 1
        assert len(losers) == 1

        print(
            "PASS: exactly one concurrent "
            "reclaim caller wins."
        )

        async with session_factory() as session:
            stored = await service.get_by_key(
                session,
                authorized_key,
            )

            assert stored is not None
            assert stored.status == "in_progress"
            assert stored.retry_authorized is False
            assert stored.error is None
            assert stored.completed_at is None
            assert stored.started_at is not None

        print(
            "PASS: successful reclaim resets "
            "operation to IN_PROGRESS."
        )

        unauthorized_key = build_idempotency_key(
            OperationType.UPLOAD_VIDEO,
            "unauthorized-retry-video",
        )

        async with session_factory() as session:
            record, created = await service.claim(
                session,
                idempotency_key=unauthorized_key,
                operation_type=(
                    OperationType
                    .UPLOAD_VIDEO
                    .value
                ),
                resource_id="unauthorized-retry-video",
            )

            assert created is True

            await service.fail(
                session,
                record,
                error="unknown_external_state",
            )

        async with session_factory() as session:
            record, reclaimed = (
                await service.reclaim_failed(
                    session,
                    idempotency_key=unauthorized_key,
                )
            )

            assert reclaimed is False
            assert record is not None
            assert record.status == "failed"
            assert record.retry_authorized is False

        print(
            "PASS: unauthorized failed "
            "operation cannot be reclaimed."
        )

        completed_key = build_idempotency_key(
            OperationType.UPLOAD_VIDEO,
            "completed-retry-video",
        )

        async with session_factory() as session:
            record, created = await service.claim(
                session,
                idempotency_key=completed_key,
                operation_type=(
                    OperationType
                    .UPLOAD_VIDEO
                    .value
                ),
                resource_id="completed-retry-video",
            )

            assert created is True

            await service.complete(
                session,
                record,
                result={
                    "external_id": "youtube-complete",
                },
            )

        async with session_factory() as session:
            record, reclaimed = (
                await service.reclaim_failed(
                    session,
                    idempotency_key=completed_key,
                )
            )

            assert reclaimed is False
            assert record is not None
            assert record.status == "completed"

        print(
            "PASS: completed operation "
            "cannot be reclaimed."
        )

        print()
        print("=" * 70)
        print(
            "ALL PRODUCTION OPERATION "
            "RECLAIM TESTS PASSED"
        )

    finally:
        await engine.dispose()

        try:
            os.remove(path)
        except PermissionError:
            pass


if __name__ == "__main__":
    asyncio.run(main())
