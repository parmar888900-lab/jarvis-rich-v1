"""Tests for the idempotent production operation executor."""

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
)
from backend.services.orchestration.idempotent_operation_executor import (
    IdempotentOperationExecutor,
)


async def main():
    print("=" * 70)
    print(
        "IDEMPOTENT OPERATION "
        "EXECUTOR TEST"
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

    try:
        async with engine.begin() as conn:
            await conn.run_sync(
                Base.metadata.create_all
            )

        executor = IdempotentOperationExecutor(
            session_factory
        )

        calls = 0

        async def successful_operation():
            nonlocal calls
            calls += 1

            return {
                "external_id": "youtube-123",
            }

        first = await executor.execute(
            operation_type=(
                OperationType.UPLOAD_VIDEO
            ),
            resource_id="video-123",
            operation=successful_operation,
        )

        second = await executor.execute(
            operation_type=(
                OperationType.UPLOAD_VIDEO
            ),
            resource_id="video-123",
            operation=successful_operation,
        )

        assert calls == 1

        assert first["executed"] is True
        assert second["executed"] is False

        assert (
            second["result"]["external_id"]
            == "youtube-123"
        )

        print(
            "PASS: completed operation "
            "is not executed twice."
        )

        failure_calls = 0

        async def failing_operation():
            nonlocal failure_calls
            failure_calls += 1

            raise ConnectionError(
                "provider unavailable"
            )

        try:
            await executor.execute(
                operation_type=(
                    OperationType.UPLOAD_VIDEO
                ),
                resource_id="video-failure",
                operation=failing_operation,
            )
        except ConnectionError:
            pass
        else:
            raise AssertionError(
                "Operation exception "
                "did not propagate."
            )

        failed_again = await executor.execute(
            operation_type=(
                OperationType.UPLOAD_VIDEO
            ),
            resource_id="video-failure",
            operation=failing_operation,
        )

        assert failure_calls == 1
        assert (
            failed_again["status"]
            == "failed"
        )
        assert (
            failed_again["executed"]
            is False
        )

        print(
            "PASS: failed operation is "
            "not blindly re-executed."
        )

        cancellation_started = (
            asyncio.Event()
        )

        async def cancelled_operation():
            cancellation_started.set()

            await asyncio.sleep(30)

            return {
                "impossible": True,
            }

        task = asyncio.create_task(
            executor.execute(
                operation_type=(
                    OperationType.UPLOAD_VIDEO
                ),
                resource_id="video-cancelled",
                operation=cancelled_operation,
            )
        )

        await asyncio.wait_for(
            cancellation_started.wait(),
            timeout=2,
        )

        task.cancel()

        try:
            await task
        except asyncio.CancelledError:
            pass
        else:
            raise AssertionError(
                "Cancellation did not propagate."
            )

        cancelled_again = (
            await executor.execute(
                operation_type=(
                    OperationType.UPLOAD_VIDEO
                ),
                resource_id="video-cancelled",
                operation=cancelled_operation,
            )
        )

        assert (
            cancelled_again["status"]
            == "failed"
        )
        assert (
            cancelled_again["error"]
            == "operation_cancelled"
        )

        print(
            "PASS: cancellation propagates "
            "and leaves a terminal record."
        )

        print()
        print("=" * 70)
        print(
            "ALL IDEMPOTENT OPERATION "
            "EXECUTOR TESTS PASSED"
        )

    finally:
        await engine.dispose()

        try:
            os.remove(path)
        except PermissionError:
            pass


if __name__ == "__main__":
    asyncio.run(main())
