"""Shared execution service for production cycles."""

import asyncio
from collections.abc import Callable
from contextlib import suppress
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from backend.services.orchestration.production_runtime import (
    production_lock,
)


class ProductionCycleBusyError(RuntimeError):
    """Raised when another production cycle is already running."""


class ProductionRunner:
    """Run production cycles through one shared concurrency gate."""

    HEARTBEAT_PATH = Path(
        "generated/state/production_active.json"
    )

    HEARTBEAT_SECONDS = 15

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

        self.HEARTBEAT_PATH.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

    def _write_heartbeat(
        self,
        cycle_id: str,
    ) -> None:

        import json

        temporary = self.HEARTBEAT_PATH.with_suffix(
            ".tmp"
        )

        temporary.write_text(
            json.dumps(
                {
                    "cycle_id": cycle_id,
                    "pid": __import__("os").getpid(),
                    "updated_at": datetime.now(
                        timezone.utc
                    ).isoformat(),
                },
                indent=2,
            ),
            encoding="utf-8",
        )

        temporary.replace(
            self.HEARTBEAT_PATH
        )

    async def _heartbeat_loop(
        self,
        cycle_id: str,
    ) -> None:

        while True:

            self._write_heartbeat(
                cycle_id
            )

            await asyncio.sleep(
                self.HEARTBEAT_SECONDS
            )

    async def run_cycle(self) -> dict:
        """Run one production cycle or reject if busy."""

        if self.lock.locked():
            raise ProductionCycleBusyError(
                "Another production cycle is already running."
            )

        await self.lock.acquire()

        cycle_id = self.cycle_id_factory()

        self._write_heartbeat(
            cycle_id
        )

        heartbeat_task = asyncio.create_task(
            self._heartbeat_loop(
                cycle_id
            ),
            name=f"production-heartbeat-{cycle_id}",
        )

        try:

            return await self.orchestrator.run_cycle(
                cycle_id
            )

        finally:

            heartbeat_task.cancel()

            with suppress(asyncio.CancelledError):
                await heartbeat_task

            with suppress(
                FileNotFoundError,
                PermissionError,
            ):
                self.HEARTBEAT_PATH.unlink()

            self.lock.release()
