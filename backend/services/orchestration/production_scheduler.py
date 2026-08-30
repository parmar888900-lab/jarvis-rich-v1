"""Autonomous production scheduler."""

import asyncio
import logging
from typing import Any

from backend.services.orchestration.autonomous_retry import (
    AutonomousRetryPolicy,
)
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
        retry_policy: AutonomousRetryPolicy | None = None,
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
        self.retry_policy = (
            retry_policy
            if retry_policy is not None
            else AutonomousRetryPolicy()
        )
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

    def enable(self) -> bool:
        """Enable autonomous production and start scheduling."""

        was_enabled = self.enabled
        self.enabled = True

        started = self.start()

        return (
            not was_enabled
            or started
        )

    async def disable(self) -> bool:
        """Disable autonomous production and stop scheduling."""

        changed = self.enabled or self.running

        self.enabled = False

        if self.running:
            await self.stop()

        return changed

    async def run_once(self) -> dict:
        """Attempt one autonomous production cycle with safe retries."""

        attempt = 1

        while True:
            try:
                result = await self.runner.run_cycle()

                return {
                    "status": result.get(
                        "status",
                        "success",
                    ),
                    "attempts": attempt,
                    "result": result,
                }

            except ProductionCycleBusyError:
                return {
                    "status": "skipped",
                    "reason": "production_busy",
                    "attempts": attempt,
                }

            except asyncio.CancelledError:
                raise

            except Exception as exc:
                should_retry = (
                    self.retry_policy.is_retryable_exception(
                        exc
                    )
                    and attempt
                    < self.retry_policy.max_attempts
                )

                if not should_retry:
                    logger.exception(
                        "Scheduled production cycle failed."
                    )

                    return {
                        "status": "scheduler_failed",
                        "reason": "production_cycle_failed",
                        "attempts": attempt,
                        "error_type": type(exc).__name__,
                    }

                delay = (
                    self.retry_policy.delay_for_retry(
                        attempt
                    )
                )

                logger.warning(
                    "Transient production failure on "
                    "attempt %s/%s. Retrying in %.2fs.",
                    attempt,
                    self.retry_policy.max_attempts,
                    delay,
                )

                await asyncio.sleep(
                    delay
                )

                attempt += 1

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
