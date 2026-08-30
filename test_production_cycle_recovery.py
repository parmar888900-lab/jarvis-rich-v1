"""Tests for stale production-cycle recovery."""

import asyncio
import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy.ext.asyncio import (
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
            Path(temp_dir)
            / "production_recovery_test.db"
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
                ProductionCycleRecord
                .__table__
                .create
            )

        service = ProductionCycleService()

        now = datetime(
            2026,
            8,
            30,
            15,
            0,
            0,
        )

        async with session_factory() as session:
            old_started = ProductionCycleRecord(
                id="stale-cycle",
                status=ProductionCycleStatus.STARTED,
                started_at=(
                    now
                    - timedelta(hours=7)
                ),
            )

            recent_started = ProductionCycleRecord(
                id="recent-cycle",
                status=ProductionCycleStatus.STARTED,
                started_at=(
                    now
                    - timedelta(minutes=30)
                ),
            )

            completed = ProductionCycleRecord(
                id="completed-cycle",
                status=ProductionCycleStatus.COMPLETED,
                started_at=(
                    now
                    - timedelta(hours=10)
                ),
                completed_at=(
                    now
                    - timedelta(hours=9)
                ),
                result='{"status":"success"}',
            )

            session.add_all(
                [
                    old_started,
                    recent_started,
                    completed,
                ]
            )

            await session.commit()

        print("=" * 70)
        print("STALE CYCLE RECOVERY TEST")
        print()

        async with session_factory() as session:
            recovered = (
                await service.recover_stale_cycles(
                    session,
                    stale_after=timedelta(
                        hours=6
                    ),
                    now=now,
                )
            )

        assert len(recovered) == 1
        assert recovered[0].id == "stale-cycle"

        async with session_factory() as session:
            stale = await service.get_cycle(
                session,
                "stale-cycle",
            )

            recent = await service.get_cycle(
                session,
                "recent-cycle",
            )

            terminal = await service.get_cycle(
                session,
                "completed-cycle",
            )

        assert (
            stale.status
            == ProductionCycleStatus.FAILED
        )

        assert stale.completed_at == now

        payload = json.loads(
            stale.result
        )

        assert (
            payload["error"]
            == "stale_cycle_recovered"
        )

        assert (
            payload["recovery"]
            ["stale_after_seconds"]
            == 21600.0
        )

        assert (
            recent.status
            == ProductionCycleStatus.STARTED
        )

        assert recent.completed_at is None

        assert (
            terminal.status
            == ProductionCycleStatus.COMPLETED
        )

        print(
            "RECOVERED:",
            [cycle.id for cycle in recovered],
        )
        print(
            "STALE STATUS:",
            stale.status.value,
        )
        print(
            "RECENT STATUS:",
            recent.status.value,
        )
        print(
            "TERMINAL STATUS:",
            terminal.status.value,
        )
        print()
        print(
            "PASS: only stale STARTED cycles "
            "are recovered as FAILED."
        )

        print()
        print("=" * 70)
        print("NO STALE CYCLES TEST")
        print()

        async with session_factory() as session:
            recovered_again = (
                await service.recover_stale_cycles(
                    session,
                    stale_after=timedelta(
                        hours=6
                    ),
                    now=now,
                )
            )

        assert recovered_again == []

        print(
            "RECOVERED:",
            len(recovered_again),
        )
        print()
        print(
            "PASS: recovery is idempotent "
            "after stale cycles are terminal."
        )

        print()
        print("=" * 70)
        print("INVALID RECOVERY WINDOW TEST")
        print()

        async with session_factory() as session:
            try:
                await service.recover_stale_cycles(
                    session,
                    stale_after=timedelta(
                        seconds=0
                    ),
                    now=now,
                )
            except ValueError as exc:
                assert (
                    "greater than zero"
                    in str(exc)
                )
            else:
                raise AssertionError(
                    "Zero stale interval "
                    "was accepted."
                )

        print(
            "PASS: invalid stale intervals "
            "are rejected."
        )

        await engine.dispose()

        print()
        print("=" * 70)
        print(
            "ALL STALE CYCLE "
            "RECOVERY TESTS PASSED"
        )


if __name__ == "__main__":
    asyncio.run(main())
