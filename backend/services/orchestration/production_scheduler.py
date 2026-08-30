"""Autonomous production scheduler."""

import asyncio
import logging
from typing import Any

from backend.services.orchestration.production_runner import (
    ProductionCycleBusyError,
    ProductionRunner,
)

logger = logging.getLogger(__name__)


class ProductionScheduler:
    """Periodically launch production cycles."""

    def __init__(
        self,
        orchestrator: Any,
        *,
        interval_seconds: float,
        enabled: bool = False,
    ) -> None:

        if interval_seconds <= 0:
            raise ValueError(
                "interval_seconds must be greater than zero."
            )

        self.orchestrator = orchestrator
        self.runner = ProductionRunner(
            orchestrator
        )

        self.interval_seconds = float(
            interval_seconds
        )
        self.enabled = enabled
        self._task: asyncio.Task | None = None

    @property
    def running(self) -> bool:
        return (
            self._task is not None
            and not self._task.done()
        )

    def start(self) -> bool:
        """Start the scheduler when enabled."""

        if not self.enabled:
            return False

        if self.running:
            return False

        self._task = asyncio.create_task(
            self._run_loop(),
            name="production-scheduler",
        )

        return True

    async def stop(self) -> bool:
        """Stop the scheduler cleanly."""

        if self._task is None:
            return False

        task = self._task
        self._task = None

        if task.done():
            try:
                task.result()
            except asyncio.CancelledError:
                pass
            except Exception:
                logger.exception(
                    "Production scheduler task failed."
                )

            return True

        task.cancel()

        try:
            await task
        except asyncio.CancelledError:
            pass

        return True

    async def run_once(self) -> dict:
        """Attempt one autonomous production cycle."""

        try:
            return await self.runner.run_cycle()

        except ProductionCycleBusyError:
            return {
                "status": "skipped",
                "reason": "production_busy",
            }

        except asyncio.CancelledError:
            raise

        except Exception:
            logger.exception(
                "Scheduled production cycle failed."
            )

            return {
                "status": "scheduler_failed",
                "reason": "production_cycle_failed",
            }

    async def _run_loop(self) -> None:
        """Run scheduled cycles until cancelled."""

        while True:
            await asyncio.sleep(
                self.interval_seconds
            )

            try:
                await self.run_once()

            except asyncio.CancelledError:
                raise

            except Exception:
                logger.exception(
                    "Unexpected scheduler-loop failure."
                )
