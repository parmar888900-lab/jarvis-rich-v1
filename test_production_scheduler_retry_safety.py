"""Safety tests for autonomous retry cancellation and lock release."""

import asyncio

from backend.services.orchestration.autonomous_retry import (
    AutonomousRetryPolicy,
)
from backend.services.orchestration.production_runtime import (
    production_lock,
)
from backend.services.orchestration.production_scheduler import (
    ProductionScheduler,
)


class OneTransientFailureOrchestrator:
    def __init__(self):
        self.calls = 0
        self.failed = asyncio.Event()

    async def run_cycle(self, cycle_id):
        self.calls += 1

        if self.calls == 1:
            self.failed.set()

            raise TimeoutError(
                "temporary timeout"
            )

        return {
            "cycle_id": cycle_id,
            "status": "success",
        }


class AlwaysTransientFailureOrchestrator:
    def __init__(self):
        self.calls = 0

    async def run_cycle(self, cycle_id):
        self.calls += 1

        raise ConnectionError(
            "temporary connection failure"
        )


async def test_cancellation_during_backoff():
    orchestrator = (
        OneTransientFailureOrchestrator()
    )

    scheduler = ProductionScheduler(
        orchestrator,
        interval_seconds=3600,
        retry_policy=AutonomousRetryPolicy(
            max_attempts=3,
            base_delay_seconds=30,
        ),
    )

    task = asyncio.create_task(
        scheduler.run_once()
    )

    await asyncio.wait_for(
        orchestrator.failed.wait(),
        timeout=2,
    )

    await asyncio.sleep(0)

    assert production_lock.locked() is False

    task.cancel()

    try:
        await task
    except asyncio.CancelledError:
        pass
    else:
        raise AssertionError(
            "Cancellation did not propagate."
        )

    assert orchestrator.calls == 1
    assert production_lock.locked() is False

    print(
        "PASS: cancellation during backoff "
        "propagates immediately."
    )


async def test_lock_release_after_exhaustion():
    orchestrator = (
        AlwaysTransientFailureOrchestrator()
    )

    scheduler = ProductionScheduler(
        orchestrator,
        interval_seconds=3600,
        retry_policy=AutonomousRetryPolicy(
            max_attempts=3,
            base_delay_seconds=0,
        ),
    )

    result = await scheduler.run_once()

    assert result["status"] == "scheduler_failed"
    assert result["attempts"] == 3
    assert orchestrator.calls == 3

    assert production_lock.locked() is False

    print(
        "PASS: retry exhaustion leaves "
        "the shared production lock released."
    )


async def test_lock_reusable_after_retry_failure():
    failing = (
        AlwaysTransientFailureOrchestrator()
    )

    failing_scheduler = ProductionScheduler(
        failing,
        interval_seconds=3600,
        retry_policy=AutonomousRetryPolicy(
            max_attempts=1,
            base_delay_seconds=0,
        ),
    )

    failed = await failing_scheduler.run_once()

    assert failed["status"] == "scheduler_failed"
    assert production_lock.locked() is False

    succeeding = (
        OneTransientFailureOrchestrator()
    )

    succeeding.calls = 1

    success_scheduler = ProductionScheduler(
        succeeding,
        interval_seconds=3600,
        retry_policy=AutonomousRetryPolicy(
            max_attempts=1,
            base_delay_seconds=0,
        ),
    )

    success = await success_scheduler.run_once()

    assert success["status"] == "success"
    assert production_lock.locked() is False

    print(
        "PASS: production lock remains "
        "reusable after autonomous failure."
    )


async def main():
    print("=" * 70)
    print(
        "AUTONOMOUS RETRY SAFETY TEST"
    )
    print()

    await test_cancellation_during_backoff()
    await test_lock_release_after_exhaustion()
    await test_lock_reusable_after_retry_failure()

    print()
    print("=" * 70)
    print(
        "ALL AUTONOMOUS RETRY "
        "SAFETY TESTS PASSED"
    )


if __name__ == "__main__":
    asyncio.run(main())
