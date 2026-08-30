import asyncio
import tempfile
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    async_sessionmaker,
    create_async_engine,
)

from backend.database import Base
from backend.models.production_cycle import (
    ProductionCycleRecord,
    ProductionCycleStatus,
)
from backend.services.orchestration.production_orchestrator import (
    ProductionOrchestrator,
)
from backend.services.production_cycle_service import (
    ProductionCycleService,
)


class SuccessCommander:
    async def route(
        self,
        agent,
        task,
        command_id,
        parameters=None,
    ):
        if task == "analyze_trends":
            return {
                "status": "success",
                "best_trend": {
                    "title": "Persistent integration topic",
                    "production_selection": {
                        "eligible": True,
                        "selected": True,
                        "production_score": 92.5,
                    },
                },
            }

        if task == "create_video":
            return {
                "status": "success",
                "production_package": {
                    "video_path": "generated/integration.mp4",
                },
            }

        raise AssertionError(
            f"Unexpected task: {task}"
        )


class NoActionCommander:
    async def route(
        self,
        agent,
        task,
        command_id,
        parameters=None,
    ):
        return {
            "status": "no_production_ready_topic",
        }


class ProductionFailureCommander:
    async def route(
        self,
        agent,
        task,
        command_id,
        parameters=None,
    ):
        if task == "analyze_trends":
            return {
                "status": "success",
                "best_trend": {
                    "title": "Failure integration topic",
                    "production_selection": {
                        "eligible": True,
                        "selected": True,
                        "production_score": 77.0,
                    },
                },
            }

        if task == "create_video":
            return {
                "status": "production_error",
                "error": "Fake integration failure",
            }

        raise AssertionError(
            f"Unexpected task: {task}"
        )


class ExplodingCommander:
    async def route(
        self,
        agent,
        task,
        command_id,
        parameters=None,
    ):
        raise RuntimeError(
            "Unexpected integration crash"
        )


async def get_record(
    session_factory,
    cycle_id,
):
    async with session_factory() as session:
        result = await session.execute(
            select(
                ProductionCycleRecord
            ).where(
                ProductionCycleRecord.id
                == cycle_id
            )
        )

        return result.scalar_one()


async def main():
    with tempfile.TemporaryDirectory() as temp_dir:
        database_path = (
            Path(temp_dir)
            / "production_cycle_test.db"
        )

        engine = create_async_engine(
            (
                "sqlite+aiosqlite:///"
                f"{database_path.as_posix()}"
            ),
            echo=False,
        )

        session_factory = async_sessionmaker(
            bind=engine,
            expire_on_commit=False,
        )

        async with engine.begin() as conn:
            await conn.run_sync(
                Base.metadata.create_all
            )

        service = ProductionCycleService()

        print("=" * 70)
        print("REAL SQLITE SUCCESS TEST")
        print()

        success = ProductionOrchestrator(
            commander=SuccessCommander(),
            cycle_service=service,
            session_factory=session_factory,
        )

        result = await success.run_cycle(
            "integration-success"
        )

        record = await get_record(
            session_factory,
            "integration-success",
        )

        assert result["status"] == "success"

        assert (
            record.status
            == ProductionCycleStatus.COMPLETED
        )

        assert (
            record.selected_topic
            == "Persistent integration topic"
        )

        assert (
            record.production_score
            == 92.5
        )

        assert record.completed_at is not None
        assert record.result is not None

        print(
            "STATUS:",
            record.status.value,
        )
        print(
            "TOPIC:",
            record.selected_topic,
        )
        print(
            "SCORE:",
            record.production_score,
        )
        print()
        print(
            "PASS: successful orchestration "
            "is persisted as COMPLETED."
        )

        print()
        print("=" * 70)
        print("REAL SQLITE NO ACTION TEST")
        print()

        no_action = ProductionOrchestrator(
            commander=NoActionCommander(),
            cycle_service=service,
            session_factory=session_factory,
        )

        result = await no_action.run_cycle(
            "integration-no-action"
        )

        record = await get_record(
            session_factory,
            "integration-no-action",
        )

        assert (
            result["status"]
            == "no_action"
        )

        assert (
            record.status
            == ProductionCycleStatus.NO_ACTION
        )

        assert record.completed_at is not None
        assert record.result is not None

        print(
            "STATUS:",
            record.status.value,
        )
        print(
            "REASON:",
            result["reason"],
        )
        print()
        print(
            "PASS: normal lack of a suitable "
            "topic is persisted as NO_ACTION."
        )

        print()
        print("=" * 70)
        print("REAL SQLITE FAILURE TEST")
        print()

        failure = ProductionOrchestrator(
            commander=ProductionFailureCommander(),
            cycle_service=service,
            session_factory=session_factory,
        )

        result = await failure.run_cycle(
            "integration-failure"
        )

        record = await get_record(
            session_factory,
            "integration-failure",
        )

        assert (
            result["status"]
            == "production_failed"
        )

        assert (
            record.status
            == ProductionCycleStatus.FAILED
        )

        assert record.completed_at is not None
        assert record.result is not None

        print(
            "STATUS:",
            record.status.value,
        )
        print()
        print(
            "PASS: production failure "
            "is persisted as FAILED."
        )

        print()
        print("=" * 70)
        print("REAL SQLITE EXCEPTION TEST")
        print()

        exploding = ProductionOrchestrator(
            commander=ExplodingCommander(),
            cycle_service=service,
            session_factory=session_factory,
        )

        try:
            await exploding.run_cycle(
                "integration-exception"
            )
        except RuntimeError as exc:
            assert (
                str(exc)
                == "Unexpected integration crash"
            )
        else:
            raise AssertionError(
                "Expected RuntimeError was not raised."
            )

        record = await get_record(
            session_factory,
            "integration-exception",
        )

        assert (
            record.status
            == ProductionCycleStatus.FAILED
        )

        assert record.completed_at is not None
        assert record.result is not None

        print(
            "STATUS:",
            record.status.value,
        )
        print()
        print(
            "PASS: unexpected exception is "
            "persisted as FAILED and re-raised."
        )

        print()
        print("=" * 70)
        print("DUPLICATE CYCLE TEST")
        print()

        duplicate = ProductionOrchestrator(
            commander=SuccessCommander(),
            cycle_service=service,
            session_factory=session_factory,
        )

        try:
            await duplicate.run_cycle(
                "integration-success"
            )
        except ValueError as exc:
            assert (
                "already exists"
                in str(exc)
            )
        else:
            raise AssertionError(
                "Duplicate cycle ID was accepted."
            )

        print(
            "PASS: duplicate cycle IDs "
            "are rejected before a second "
            "production run begins."
        )

        await engine.dispose()

        print()
        print("=" * 70)
        print(
            "ALL REAL SQLITE "
            "PERSISTENCE TESTS PASSED"
        )


if __name__ == "__main__":
    asyncio.run(main())
