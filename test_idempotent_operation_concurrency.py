"""Concurrency tests for the idempotent operation executor."""

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
        "IDEMPOTENT EXECUTOR "
        "CONCURRENCY TEST"
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

        operation_started = asyncio.Event()
        allow_completion = asyncio.Event()

        first_calls = 0
        second_calls = 0

        async def first_operation():
            nonlocal first_calls
            first_calls += 1

            operation_started.set()

            await allow_completion.wait()

            return {
                "external_id": "youtube-789",
            }

        async def second_operation():
            nonlocal second_calls
            second_calls += 1

            return {
                "external_id": "DUPLICATE",
            }

        first_task = asyncio.create_task(
            executor.execute(
                operation_type=(
                    OperationType.UPLOAD_VIDEO
                ),
                resource_id=(
                    "concurrent-video"
                ),
                operation=first_operation,
            )
        )

        await asyncio.wait_for(
            operation_started.wait(),
            timeout=2,
        )

        second_result = (
            await executor.execute(
                operation_type=(
                    OperationType.UPLOAD_VIDEO
                ),
                resource_id=(
                    "concurrent-video"
                ),
                operation=second_operation,
            )
        )

        assert (
            second_result["status"]
            == "in_progress"
        )
        assert (
            second_result["executed"]
            is False
        )

        assert first_calls == 1
        assert second_calls == 0

        print(
            "PASS: concurrent duplicate "
            "observes in-progress state."
        )
        print(
            "PASS: duplicate side-effect "
            "function was never invoked."
        )

        allow_completion.set()

        first_result = await asyncio.wait_for(
            first_task,
            timeout=2,
        )

        assert (
            first_result["status"]
            == "completed"
        )
        assert (
            first_result["executed"]
            is True
        )

        assert (
            first_result["result"][
                "external_id"
            ]
            == "youtube-789"
        )

        third_calls = 0

        async def third_operation():
            nonlocal third_calls
            third_calls += 1

            return {
                "external_id": "DUPLICATE-2",
            }

        third_result = (
            await executor.execute(
                operation_type=(
                    OperationType.UPLOAD_VIDEO
                ),
                resource_id=(
                    "concurrent-video"
                ),
                operation=third_operation,
            )
        )

        assert (
            third_result["status"]
            == "completed"
        )
        assert (
            third_result["executed"]
            is False
        )

        assert third_calls == 0

        assert (
            third_result["result"][
                "external_id"
            ]
            == "youtube-789"
        )

        print(
            "PASS: original operation "
            "completed normally."
        )
        print(
            "PASS: later duplicate returns "
            "the persisted result."
        )
        print(
            "PASS: completed side effect "
            "remains single-execution."
        )

        print()
        print("=" * 70)
        print(
            "ALL IDEMPOTENT EXECUTOR "
            "CONCURRENCY TESTS PASSED"
        )

    finally:
        allow_completion.set()

        await engine.dispose()

        try:
            os.remove(path)
        except PermissionError:
            pass


if __name__ == "__main__":
    asyncio.run(main())
