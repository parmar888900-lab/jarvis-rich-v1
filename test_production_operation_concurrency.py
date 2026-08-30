"""Concurrency tests for persistent production operation claims."""

import asyncio
import os
import tempfile

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
from backend.services.orchestration.production_operation_service import (
    ProductionOperationService,
)


async def main():
    print("=" * 70)
    print(
        "PRODUCTION OPERATION "
        "CONCURRENCY TEST"
    )
    print()

    fd, path = tempfile.mkstemp(
        suffix=".db"
    )

    os.close(fd)

    database_url = (
        f"sqlite+aiosqlite:///{path}"
    )

    engine = create_async_engine(
        database_url,
        connect_args={
            "timeout": 30,
        },
    )

    session_factory = async_sessionmaker(
        engine,
        expire_on_commit=False,
    )

    try:
        async with engine.begin() as conn:
            await conn.run_sync(
                Base.metadata.create_all
            )

        service = ProductionOperationService()

        key = build_idempotency_key(
            OperationType.UPLOAD_VIDEO,
            "video-concurrency-test",
        )

        async def claim_once():
            async with session_factory() as session:
                return await service.claim(
                    session,
                    idempotency_key=key,
                    operation_type=(
                        OperationType
                        .UPLOAD_VIDEO
                        .value
                    ),
                    resource_id=(
                        "video-concurrency-test"
                    ),
                )

        first, second = await asyncio.gather(
            claim_once(),
            claim_once(),
        )

        records = [
            first,
            second,
        ]

        created_count = sum(
            1
            for _, created in records
            if created
        )

        existing_count = sum(
            1
            for _, created in records
            if not created
        )

        assert created_count == 1
        assert existing_count == 1

        first_record = first[0]
        second_record = second[0]

        assert (
            first_record.id
            == second_record.id
        )

        assert (
            first_record.idempotency_key
            == key
        )

        async with session_factory() as session:
            stored = await service.get_by_key(
                session,
                key,
            )

            assert stored is not None
            assert (
                stored.status
                == "in_progress"
            )

            await service.complete(
                session,
                stored,
                result={
                    "external_id": "abc123",
                },
            )

        async with session_factory() as session:
            completed = (
                await service.get_by_key(
                    session,
                    key,
                )
            )

            assert completed is not None
            assert (
                completed.status
                == "completed"
            )
            assert completed.error is None
            assert (
                '"external_id": "abc123"'
                in completed.result
            )

        print(
            "PASS: exactly one competing "
            "caller acquires the claim."
        )
        print(
            "PASS: duplicate caller receives "
            "the existing operation."
        )
        print(
            "PASS: only one database record "
            "exists for the idempotency key."
        )
        print(
            "PASS: claimed operation can "
            "transition to completed."
        )

        print()
        print("=" * 70)
        print(
            "ALL PRODUCTION OPERATION "
            "CONCURRENCY TESTS PASSED"
        )

    finally:
        await engine.dispose()

        try:
            os.remove(path)
        except PermissionError:
            pass


if __name__ == "__main__":
    asyncio.run(main())
