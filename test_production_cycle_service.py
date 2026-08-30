"""Isolated tests for ProductionCycleService."""

import asyncio
import json
import tempfile
from pathlib import Path

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from backend.database import Base
from backend.models.production_cycle import (
    ProductionCycleRecord,
    ProductionCycleStatus,
)
from backend.services.production_cycle_service import (
    ProductionCycleService,
)


async def main():
    with tempfile.TemporaryDirectory() as temp_dir:
        database_path = (
            Path(temp_dir) / "production_cycle_test.db"
        )

        engine = create_async_engine(
            f"sqlite+aiosqlite:///{database_path}"
        )

        session_factory = async_sessionmaker(
            bind=engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

        async with engine.begin() as connection:
            await connection.run_sync(
                ProductionCycleRecord.__table__.create
            )

        service = ProductionCycleService()

        async with session_factory() as session:
            print("=" * 70)
            print("PRODUCTION CYCLE START TEST")
            print()

            cycle = await service.start_cycle(
                session,
                cycle_id="cycle-persistence-001",
            )

            assert cycle.id == "cycle-persistence-001"
            assert (
                cycle.status
                == ProductionCycleStatus.STARTED
            )
            assert cycle.completed_at is None

            print("STATUS:", cycle.status.value)
            print("ID:", cycle.id)
            print()
            print(
                "PASS: production cycle is persisted "
                "in STARTED state."
            )

            print()
            print("=" * 70)
            print("DUPLICATE CYCLE TEST")
            print()

            try:
                await service.start_cycle(
                    session,
                    cycle_id="cycle-persistence-001",
                )
            except ValueError as exc:
                assert "already exists" in str(exc)
                print("REJECTED:", str(exc))
            else:
                raise AssertionError(
                    "Duplicate cycle ID was accepted."
                )

            print()
            print(
                "PASS: duplicate cycle IDs are rejected."
            )

            print()
            print("=" * 70)
            print("COMPLETE CYCLE TEST")
            print()

            result = {
                "status": "success",
                "selected_trend": {
                    "title": "Persistent test topic",
                },
            }

            cycle = await service.complete_cycle(
                session,
                "cycle-persistence-001",
                selected_topic="Persistent test topic",
                production_score=91.25,
                result=result,
            )

            assert (
                cycle.status
                == ProductionCycleStatus.COMPLETED
            )
            assert (
                cycle.selected_topic
                == "Persistent test topic"
            )
            assert cycle.production_score == 91.25
            assert cycle.completed_at is not None
            assert json.loads(cycle.result) == result

            print("STATUS:", cycle.status.value)
            print("TOPIC:", cycle.selected_topic)
            print(
                "PRODUCTION SCORE:",
                cycle.production_score,
            )
            print()
            print(
                "PASS: completed production cycle "
                "stores topic, score, result and timestamp."
            )

            print()
            print("=" * 70)
            print("NO ACTION TEST")
            print()

            await service.start_cycle(
                session,
                cycle_id="cycle-persistence-002",
            )

            no_action_result = {
                "status": "no_production_ready_topic",
            }

            cycle = await service.mark_no_action(
                session,
                "cycle-persistence-002",
                result=no_action_result,
            )

            assert (
                cycle.status
                == ProductionCycleStatus.NO_ACTION
            )
            assert cycle.completed_at is not None
            assert (
                json.loads(cycle.result)
                == no_action_result
            )

            print("STATUS:", cycle.status.value)
            print()
            print(
                "PASS: no-action cycle is persisted "
                "as a terminal state."
            )

            print()
            print("=" * 70)
            print("FAILED CYCLE TEST")
            print()

            await service.start_cycle(
                session,
                cycle_id="cycle-persistence-003",
            )

            failure_result = {
                "status": "production_failed",
                "error": "Fake failure",
            }

            cycle = await service.fail_cycle(
                session,
                "cycle-persistence-003",
                result=failure_result,
            )

            assert (
                cycle.status
                == ProductionCycleStatus.FAILED
            )
            assert cycle.completed_at is not None
            assert (
                json.loads(cycle.result)
                == failure_result
            )

            print("STATUS:", cycle.status.value)
            print()
            print(
                "PASS: failed cycle is persisted "
                "as a terminal state."
            )

            print()
            print("=" * 70)
            print("LIST CYCLES TEST")
            print()

            cycles = await service.list_cycles(
                session
            )

            assert len(cycles) == 3

            completed = await service.list_cycles(
                session,
                status=ProductionCycleStatus.COMPLETED,
            )

            assert len(completed) == 1
            assert (
                completed[0].id
                == "cycle-persistence-001"
            )

            print("TOTAL:", len(cycles))
            print("COMPLETED:", len(completed))
            print()
            print(
                "PASS: production cycles can be "
                "listed and filtered by status."
            )

        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())


async def test_terminal_transition_rejected():
    with tempfile.TemporaryDirectory() as temp_dir:
        database_path = (
            Path(temp_dir) / "terminal_test.db"
        )

        engine = create_async_engine(
            f"sqlite+aiosqlite:///{database_path}"
        )

        session_factory = async_sessionmaker(
            bind=engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

        async with engine.begin() as connection:
            await connection.run_sync(
                ProductionCycleRecord.__table__.create
            )

        service = ProductionCycleService()

        async with session_factory() as session:
            await service.start_cycle(
                session,
                cycle_id="cycle-terminal-001",
            )

            await service.complete_cycle(
                session,
                "cycle-terminal-001",
                selected_topic="Terminal test",
                production_score=80.0,
                result={"status": "success"},
            )

            try:
                await service.fail_cycle(
                    session,
                    "cycle-terminal-001",
                    result={"status": "failed"},
                )
            except ValueError as exc:
                assert "already terminal" in str(exc)
            else:
                raise AssertionError(
                    "Terminal cycle was modified."
                )

            cycle = await service.get_cycle(
                session,
                "cycle-terminal-001",
            )

            assert (
                cycle.status
                == ProductionCycleStatus.COMPLETED
            )

            print()
            print("=" * 70)
            print("TERMINAL STATE INTEGRITY TEST")
            print()
            print("STATUS:", cycle.status.value)
            print()
            print(
                "PASS: terminal production cycles "
                "cannot be modified."
            )

        await engine.dispose()


async def test_empty_topic_rejected():
    with tempfile.TemporaryDirectory() as temp_dir:
        database_path = (
            Path(temp_dir) / "topic_test.db"
        )

        engine = create_async_engine(
            f"sqlite+aiosqlite:///{database_path}"
        )

        session_factory = async_sessionmaker(
            bind=engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

        async with engine.begin() as connection:
            await connection.run_sync(
                ProductionCycleRecord.__table__.create
            )

        service = ProductionCycleService()

        async with session_factory() as session:
            await service.start_cycle(
                session,
                cycle_id="cycle-topic-001",
            )

            try:
                await service.complete_cycle(
                    session,
                    "cycle-topic-001",
                    selected_topic="   ",
                    production_score=70.0,
                    result={"status": "success"},
                )
            except ValueError as exc:
                assert (
                    "selected_topic cannot be empty"
                    in str(exc)
                )
            else:
                raise AssertionError(
                    "Empty selected topic was accepted."
                )

            cycle = await service.get_cycle(
                session,
                "cycle-topic-001",
            )

            assert (
                cycle.status
                == ProductionCycleStatus.STARTED
            )

            print()
            print("=" * 70)
            print("EMPTY TOPIC VALIDATION TEST")
            print()
            print("STATUS:", cycle.status.value)
            print()
            print(
                "PASS: completion rejects an "
                "empty selected topic."
            )

        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(
        test_terminal_transition_rejected()
    )
    asyncio.run(
        test_empty_topic_rejected()
    )
