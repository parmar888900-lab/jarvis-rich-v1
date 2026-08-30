"""State-machine tests for persistent production operations."""

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
    print(
        "PRODUCTION OPERATION "
        "STATE MACHINE TEST"
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

    try:
        async with engine.begin() as conn:
            await conn.run_sync(
                Base.metadata.create_all
            )

        completed_key = build_idempotency_key(
            OperationType.UPLOAD_VIDEO,
            "completed-video",
        )

        async with session_factory() as session:
            completed, created = (
                await service.claim(
                    session,
                    idempotency_key=completed_key,
                    operation_type=(
                        OperationType
                        .UPLOAD_VIDEO
                        .value
                    ),
                    resource_id="completed-video",
                )
            )

            assert created is True
            assert (
                completed.status
                == "in_progress"
            )

            await service.complete(
                session,
                completed,
                result={
                    "external_id": "video-1",
                },
            )

            assert (
                completed.status
                == "completed"
            )

            try:
                await service.fail(
                    session,
                    completed,
                    error="late failure",
                )
            except ValueError:
                pass
            else:
                raise AssertionError(
                    "Completed operation "
                    "was allowed to fail."
                )

        failed_key = build_idempotency_key(
            OperationType.UPLOAD_VIDEO,
            "failed-video",
        )

        async with session_factory() as session:
            failed, created = (
                await service.claim(
                    session,
                    idempotency_key=failed_key,
                    operation_type=(
                        OperationType
                        .UPLOAD_VIDEO
                        .value
                    ),
                    resource_id="failed-video",
                )
            )

            assert created is True

            await service.fail(
                session,
                failed,
                error="provider rejected upload",
            )

            assert failed.status == "failed"

            try:
                await service.complete(
                    session,
                    failed,
                    result={
                        "external_id": "impossible",
                    },
                )
            except ValueError:
                pass
            else:
                raise AssertionError(
                    "Failed operation was "
                    "allowed to complete."
                )

        async with session_factory() as session:
            existing, created = (
                await service.claim(
                    session,
                    idempotency_key=completed_key,
                    operation_type=(
                        OperationType
                        .UPLOAD_VIDEO
                        .value
                    ),
                    resource_id="completed-video",
                )
            )

            assert created is False
            assert (
                existing.status
                == "completed"
            )

        print(
            "PASS: claimed operations begin "
            "in progress."
        )
        print(
            "PASS: completed operations "
            "cannot later fail."
        )
        print(
            "PASS: failed operations "
            "cannot later complete."
        )
        print(
            "PASS: completed operation claims "
            "return the existing record."
        )

        print()
        print("=" * 70)
        print(
            "ALL PRODUCTION OPERATION "
            "STATE MACHINE TESTS PASSED"
        )

    finally:
        await engine.dispose()

        try:
            os.remove(path)
        except PermissionError:
            pass


if __name__ == "__main__":
    asyncio.run(main())
