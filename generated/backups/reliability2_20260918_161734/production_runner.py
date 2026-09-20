"""Shared execution service for production cycles."""

import asyncio
from collections.abc import Callable
from typing import Any
from uuid import uuid4

from backend.services.orchestration.production_runtime import (
    production_lock,
)


class ProductionCycleBusyError(RuntimeError):
    """Raised when another production cycle is already running."""


class ProductionRunner:
    """Run production cycles through one shared concurrency gate."""

    def __init__(
        self,
        orchestrator: Any,
        *,
        lock: asyncio.Lock | None = None,
        cycle_id_factory: Callable[[], str] | None = None,
    ) -> None:

        self.orchestrator = orchestrator
        self.lock = (
            lock
            if lock is not None
            else production_lock
        )
        self.cycle_id_factory = (
            cycle_id_factory
            if cycle_id_factory is not None
            else lambda: str(uuid4())
        )

    async def run_cycle(self) -> dict:
        """Run one production cycle or reject if busy."""

        if self.lock.locked():
            raise ProductionCycleBusyError(
                "Another production cycle is already running."
            )

        await self.lock.acquire()

        cycle_id = self.cycle_id_factory()

        try:
            return await self.orchestrator.run_cycle(
                cycle_id
            )

        finally:
            self.lock.release()
