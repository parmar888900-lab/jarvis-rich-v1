"""Authorized retry tests for IdempotentOperationExecutor."""

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
from backend.services.orchestration.idempotent_operation_executor import (
    IdempotentOperationExecutor,
)
from backend.services.orchestration.production_operation_service import (
    ProductionOperationService,
)


async def make_environment():
    fd, db_path = tempfile.mkstemp(
        suffix=".db",
    )
    os.close(fd)

    engine = create_async_engine(
        f"sqlite+aiosqlite:///{db_path}",
        connect_args={
            "timeout": 30,
        },
    )

    session_factory = async_sessionmaker(
        engine,
        expire_on_commit=False,
    )

    async with engine.begin() as conn:
        await conn.run_sync(
            Base.metadata.create_all
        )

    return (
        db_path,
        engine,
        session_factory,
    )


async def prepare_failed_operation(
    session_factory,
    *,
    resource_id,
    retry_authorized,
):
    service = ProductionOperationService()

    key = build_idempotency_key(
        OperationType.UPLOAD_VIDEO,
        resource_id,
    )

    async with session_factory() as session:
        record, created = await service.claim(
            session,
            idempotency_key=key,
            operation_type=(
                OperationType.UPLOAD_VIDEO.value
            ),
            resource_id=resource_id,
        )

        assert created is True

        record = await service.fail(
            session,
            record,
            error="previous_attempt_failed",
        )

        record.retry_authorized = retry_authorized

        await session.commit()
        await session.refresh(record)

    return key


async def test_authorized_retry():
    (
        db_path,
        engine,
        session_factory,
    ) = await make_environment()

    try:
        service = ProductionOperationService()

        resource_id = "authorized-executor-retry"

        key = await prepare_failed_operation(
            session_factory,
            resource_id=resource_id,
            retry_authorized=True,
        )

        executor = IdempotentOperationExecutor(
            session_factory,
        )

        calls = 0

        async def operation():
            nonlocal calls
            calls += 1

            return {
                "external_id": "youtube-123",
            }

        result = await executor.execute(
            operation_type=OperationType.UPLOAD_VIDEO,
            resource_id=resource_id,
            operation=operation,
        )

        assert result["status"] == "completed"
        assert result["executed"] is True
        assert calls == 1

        async with session_factory() as session:
            stored = await service.get_by_key(
                session,
                key,
            )

            assert stored is not None
            assert stored.status == "completed"
            assert stored.retry_authorized is False
            assert stored.error is None

        duplicate = await executor.execute(
            operation_type=OperationType.UPLOAD_VIDEO,
            resource_id=resource_id,
            operation=operation,
        )

        assert duplicate["status"] == "completed"
        assert duplicate["executed"] is False
        assert duplicate["result"] == {
            "external_id": "youtube-123",
        }

        assert calls == 1

        print(
            "PASS: authorized failed operation "
            "executes exactly once and persists completion."
        )

    finally:
        await engine.dispose()

        try:
            os.remove(db_path)
        except PermissionError:
            pass


async def test_unauthorized_failure():
    (
        db_path,
        engine,
        session_factory,
    ) = await make_environment()

    try:
        resource_id = "blocked-executor-retry"

        await prepare_failed_operation(
            session_factory,
            resource_id=resource_id,
            retry_authorized=False,
        )

        executor = IdempotentOperationExecutor(
            session_factory,
        )

        calls = 0

        async def operation():
            nonlocal calls
            calls += 1

            return {
                "should_not": "execute",
            }

        result = await executor.execute(
            operation_type=OperationType.UPLOAD_VIDEO,
            resource_id=resource_id,
            operation=operation,
        )

        assert result["status"] == "failed"
        assert result["executed"] is False
        assert calls == 0

        print(
            "PASS: unauthorized failed operation "
            "remains blocked."
        )

    finally:
        await engine.dispose()

        try:
            os.remove(db_path)
        except PermissionError:
            pass


async def test_concurrent_authorized_retry():
    (
        db_path,
        engine,
        session_factory,
    ) = await make_environment()

    try:
        resource_id = "concurrent-authorized-retry"

        await prepare_failed_operation(
            session_factory,
            resource_id=resource_id,
            retry_authorized=True,
        )

        first_executor = IdempotentOperationExecutor(
            session_factory,
        )

        second_executor = IdempotentOperationExecutor(
            session_factory,
        )

        operation_started = asyncio.Event()
        release_operation = asyncio.Event()

        calls = 0

        async def operation():
            nonlocal calls

            calls += 1
            operation_started.set()

            await release_operation.wait()

            return {
                "external_id": "youtube-concurrent-1",
            }

        first_task = asyncio.create_task(
            first_executor.execute(
                operation_type=(
                    OperationType.UPLOAD_VIDEO
                ),
                resource_id=resource_id,
                operation=operation,
            )
        )

        await operation_started.wait()

        second_result = await second_executor.execute(
            operation_type=OperationType.UPLOAD_VIDEO,
            resource_id=resource_id,
            operation=operation,
        )

        assert second_result["executed"] is False

        assert second_result["status"] in {
            "in_progress",
            "completed",
        }

        release_operation.set()

        first_result = await first_task

        assert first_result["status"] == "completed"
        assert first_result["executed"] is True
        assert calls == 1

        print(
            "PASS: concurrent authorized retry "
            "executes the side effect only once."
        )

    finally:
        await engine.dispose()

        try:
            os.remove(db_path)
        except PermissionError:
            pass


async def main():
    print("=" * 70)
    print("IDEMPOTENT EXECUTOR AUTHORIZED RETRY TEST")
    print()

    await test_authorized_retry()
    await test_unauthorized_failure()
    await test_concurrent_authorized_retry()

    print()
    print("=" * 70)
    print(
        "ALL IDEMPOTENT EXECUTOR "
        "AUTHORIZED RETRY TESTS PASSED"
    )


if __name__ == "__main__":
    asyncio.run(main())
