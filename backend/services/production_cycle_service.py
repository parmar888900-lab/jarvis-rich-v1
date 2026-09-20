"""Persistence service for production cycles."""

import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.production_cycle import (
    ProductionCycleRecord,
    ProductionCycleStatus,
)


class ProductionCycleService:
    """Create and update production-cycle records."""

    async def start_cycle(
        self,
        session: AsyncSession,
        *,
        cycle_id: str,
    ) -> ProductionCycleRecord:

        cycle_id = cycle_id.strip()

        if not cycle_id:
            raise ValueError(
                "cycle_id cannot be empty."
            )

        existing = await self.get_cycle(
            session,
            cycle_id,
        )

        if existing is not None:
            raise ValueError(
                f"Production cycle already exists: {cycle_id}"
            )

        cycle = ProductionCycleRecord(
            id=cycle_id,
            status=ProductionCycleStatus.STARTED,
        )

        session.add(cycle)

        await session.commit()
        await session.refresh(cycle)

        return cycle

    async def get_cycle(
        self,
        session: AsyncSession,
        cycle_id: str,
    ) -> ProductionCycleRecord | None:

        return await session.get(
            ProductionCycleRecord,
            cycle_id,
        )

    async def list_cycles(
        self,
        session: AsyncSession,
        *,
        status: ProductionCycleStatus | None = None,
    ) -> list[ProductionCycleRecord]:

        statement = select(
            ProductionCycleRecord
        )

        if status is not None:
            statement = statement.where(
                ProductionCycleRecord.status
                == status
            )

        statement = statement.order_by(
            ProductionCycleRecord.started_at.desc()
        )

        result = await session.execute(
            statement
        )

        return list(
            result.scalars().all()
        )

    async def get_latest_cycle(
        self,
        session: AsyncSession,
    ) -> ProductionCycleRecord | None:
        """Return the most recently started production cycle."""

        statement = (
            select(
                ProductionCycleRecord
            )
            .order_by(
                ProductionCycleRecord.started_at.desc()
            )
            .limit(1)
        )

        result = await session.execute(
            statement
        )

        return result.scalars().first()

    async def complete_cycle(
        self,
        session: AsyncSession,
        cycle_id: str,
        *,
        selected_topic: str,
        production_score: float | None,
        result: dict,
    ) -> ProductionCycleRecord:

        cycle = await self._require_cycle(
            session,
            cycle_id,
        )

        self._require_started(cycle)

        selected_topic = selected_topic.strip()

        if not selected_topic:
            raise ValueError(
                "selected_topic cannot be empty."
            )

        cycle.status = (
            ProductionCycleStatus.COMPLETED
        )
        cycle.selected_topic = selected_topic
        cycle.production_score = (
            float(production_score)
            if production_score is not None
            else None
        )
        cycle.result = json.dumps(
            result,
            ensure_ascii=False,
        )
        cycle.completed_at = self._utc_now()

        await session.commit()
        await session.refresh(cycle)

        return cycle

    async def mark_no_action(
        self,
        session: AsyncSession,
        cycle_id: str,
        *,
        result: dict,
    ) -> ProductionCycleRecord:

        cycle = await self._require_cycle(
            session,
            cycle_id,
        )

        self._require_started(cycle)

        cycle.status = (
            ProductionCycleStatus.NO_ACTION
        )
        cycle.result = json.dumps(
            result,
            ensure_ascii=False,
        )
        cycle.completed_at = self._utc_now()

        await session.commit()
        await session.refresh(cycle)

        return cycle

    async def fail_cycle(
        self,
        session: AsyncSession,
        cycle_id: str,
        *,
        result: dict,
    ) -> ProductionCycleRecord:

        cycle = await self._require_cycle(
            session,
            cycle_id,
        )

        self._require_started(cycle)

        cycle.status = (
            ProductionCycleStatus.FAILED
        )
        cycle.result = json.dumps(
            result,
            ensure_ascii=False,
        )
        cycle.completed_at = self._utc_now()

        await session.commit()
        await session.refresh(cycle)

        return cycle

    async def recover_stale_cycles(
        self,
        session: AsyncSession,
        *,
        stale_after: timedelta,
        now: datetime | None = None,
    ) -> list[ProductionCycleRecord]:
        """Mark abandoned STARTED cycles as FAILED."""

        if stale_after.total_seconds() <= 0:
            raise ValueError(
                "stale_after must be greater than zero."
            )

        recovery_time = now or self._utc_now()
        cutoff = recovery_time - stale_after

        statement = (
            select(
                ProductionCycleRecord
            )
            .where(
                ProductionCycleRecord.status
                == ProductionCycleStatus.STARTED
            )
            .where(
                ProductionCycleRecord.started_at
                <= cutoff
            )
            .order_by(
                ProductionCycleRecord.started_at.asc()
            )
        )

        query_result = await session.execute(
            statement
        )

        stale_cycles = list(
            query_result.scalars().all()
        )

        for cycle in stale_cycles:
            cycle.status = (
                ProductionCycleStatus.FAILED
            )
            cycle.completed_at = recovery_time
            cycle.result = json.dumps(
                {
                    "cycle_id": cycle.id,
                    "status": "orchestration_failed",
                    "error": "stale_cycle_recovered",
                    "recovery": {
                        "reason": (
                            "Production cycle remained "
                            "STARTED beyond the allowed "
                            "stale interval."
                        ),
                        "stale_after_seconds": (
                            stale_after.total_seconds()
                        ),
                        "recovered_at": (
                            recovery_time.isoformat()
                        ),
                    },
                },
                ensure_ascii=False,
            )

        if stale_cycles:
            await session.commit()

            for cycle in stale_cycles:
                await session.refresh(
                    cycle
                )

        return stale_cycles

    @staticmethod
    def _utc_now() -> datetime:
        """Return naive UTC for SQLite DateTime consistency."""

        return datetime.now(
            timezone.utc
        ).replace(
            tzinfo=None
        )

    @staticmethod
    def _require_started(
        cycle: ProductionCycleRecord,
    ) -> None:

        if (
            cycle.status
            != ProductionCycleStatus.STARTED
        ):
            raise ValueError(
                "Production cycle is already terminal: "
                f"{cycle.id} ({cycle.status.value})"
            )

    async def _require_cycle(
        self,
        session: AsyncSession,
        cycle_id: str,
    ) -> ProductionCycleRecord:

        cycle = await self.get_cycle(
            session,
            cycle_id,
        )

        if cycle is None:
            raise ValueError(
                f"Production cycle not found: {cycle_id}"
            )

        return cycle


