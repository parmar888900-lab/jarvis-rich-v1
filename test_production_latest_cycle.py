"""Tests for latest production-cycle retrieval."""

import asyncio
from datetime import datetime, timedelta

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
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:"
    )

    session_factory = async_sessionmaker(
        engine,
        expire_on_commit=False,
    )

    async with engine.begin() as conn:
        await conn.run_sync(
            Base.metadata.create_all
        )

    service = ProductionCycleService()

    async with session_factory() as session:
        empty = await service.get_latest_cycle(
            session
        )

        assert empty is None

        first = ProductionCycleRecord(
            id="older-cycle",
            status=ProductionCycleStatus.COMPLETED,
            started_at=datetime(
                2026,
                8,
                30,
                12,
                0,
                0,
            ),
        )

        second = ProductionCycleRecord(
            id="newer-cycle",
            status=ProductionCycleStatus.STARTED,
            started_at=(
                first.started_at
                + timedelta(hours=1)
            ),
        )

        session.add_all(
            [
                first,
                second,
            ]
        )

        await session.commit()

        latest = await service.get_latest_cycle(
            session
        )

        assert latest is not None
        assert latest.id == "newer-cycle"
        assert (
            latest.status
            == ProductionCycleStatus.STARTED
        )

        print("=" * 70)
        print("LATEST PRODUCTION CYCLE TEST")
        print()
        print("LATEST ID:", latest.id)
        print(
            "LATEST STATUS:",
            latest.status.value,
        )
        print()
        print(
            "PASS: latest production cycle "
            "is retrieved without loading "
            "the full cycle history."
        )

    await engine.dispose()

    print()
    print("=" * 70)
    print(
        "ALL LATEST PRODUCTION CYCLE "
        "TESTS PASSED"
    )


if __name__ == "__main__":
    asyncio.run(main())
