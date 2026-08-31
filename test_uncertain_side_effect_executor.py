"""Regression for externally uncertain side effects."""

import asyncio
import tempfile
from pathlib import Path

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
from backend.services.orchestration.uncertain_side_effect import (
    UncertainSideEffectError,
)


async def main():

    print("=" * 72)
    print(
        "UNCERTAIN SIDE-EFFECT EXECUTOR TEST"
    )
    print("=" * 72)

    with tempfile.TemporaryDirectory() as directory:

        db_path = (
            Path(directory)
            / "operations.db"
        )

        engine = create_async_engine(
            "sqlite+aiosqlite:///"
            + db_path.as_posix()
        )

        session_factory = (
            async_sessionmaker(
                engine,
                expire_on_commit=False,
            )
        )

        async with engine.begin() as connection:
            await connection.run_sync(
                Base.metadata.create_all
            )

        executor = (
            IdempotentOperationExecutor(
                session_factory
            )
        )

        calls = 0

        async def uncertain_operation():
            nonlocal calls

            calls += 1

            raise UncertainSideEffectError(
                "provider response lost"
            )

        resource_id = (
            "youtube:test-channel:"
            "uncertain-artifact"
        )

        try:
            await executor.execute(
                operation_type=(
                    OperationType.UPLOAD_VIDEO
                ),
                resource_id=resource_id,
                operation=(
                    uncertain_operation
                ),
            )

        except UncertainSideEffectError:
            pass

        else:
            raise AssertionError(
                "Uncertain provider outcome "
                "did not propagate."
            )

        assert calls == 1

        second = await executor.execute(
            operation_type=(
                OperationType.UPLOAD_VIDEO
            ),
            resource_id=resource_id,
            operation=(
                uncertain_operation
            ),
        )

        assert (
            second["status"]
            == "reconciliation_required"
        )

        assert (
            second["executed"]
            is False
        )

        assert calls == 1

        service = (
            ProductionOperationService()
        )

        key = build_idempotency_key(
            OperationType.UPLOAD_VIDEO,
            resource_id,
        )

        async with session_factory() as session:

            record = (
                await service.get_by_key(
                    session,
                    key,
                )
            )

            assert record is not None

            assert (
                record.status
                == "reconciliation_required"
            )

            assert (
                record.retry_authorized
                is False
            )

            assert (
                record.completed_at
                is None
            )

        await engine.dispose()

    print(
        "PASS: uncertain provider outcome "
        "enters RECONCILIATION_REQUIRED."
    )

    print(
        "PASS: unresolved operation cannot "
        "execute a second time."
    )

    print(
        "PASS: unresolved operation remains "
        "non-terminal and retry-unauthorized."
    )

    print("=" * 72)


if __name__ == "__main__":
    asyncio.run(main())
