"""Persistence service for production cycles."""

import json
from datetime import datetime

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
        cycle.completed_at = datetime.now()

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
        cycle.completed_at = datetime.now()

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
        cycle.completed_at = datetime.now()

        await session.commit()
        await session.refresh(cycle)

        return cycle

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
