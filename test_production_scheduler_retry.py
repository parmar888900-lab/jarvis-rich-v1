"""Integration tests for autonomous production retries."""

import asyncio

from backend.services.orchestration.autonomous_retry import (
    AutonomousRetryPolicy,
)
from backend.services.orchestration.production_scheduler import (
    ProductionScheduler,
)


class TransientThenSuccessOrchestrator:
    def __init__(self):
        self.calls = 0

    async def run_cycle(self, cycle_id):
        self.calls += 1

        if self.calls < 3:
            raise TimeoutError(
                "temporary timeout"
            )

        return {
            "cycle_id": cycle_id,
            "status": "success",
        }


class PermanentFailureOrchestrator:
    def __init__(self):
        self.calls = 0

    async def run_cycle(self, cycle_id):
        self.calls += 1

        raise ValueError(
            "permanent failure"
        )


class AlwaysTransientFailureOrchestrator:
    def __init__(self):
        self.calls = 0

    async def run_cycle(self, cycle_id):
        self.calls += 1

        raise ConnectionError(
            "temporary connection failure"
        )


async def test_transient_retry_success():
    orchestrator = (
        TransientThenSuccessOrchestrator()
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

    assert orchestrator.calls == 3
    assert result["status"] == "success"

    # Successful retries preserve the normal
    # ProductionOrchestrator result contract.
    # Retry-attempt metadata is only added to
    # scheduler-owned failure/skip envelopes.

    print(
        "PASS: transient failures retry "
        "until success."
    )


async def test_permanent_failure_no_retry():
    orchestrator = PermanentFailureOrchestrator()

    scheduler = ProductionScheduler(
        orchestrator,
        interval_seconds=3600,
        retry_policy=AutonomousRetryPolicy(
            max_attempts=3,
            base_delay_seconds=0,
        ),
    )

    result = await scheduler.run_once()

    assert orchestrator.calls == 1
    assert result["status"] == "scheduler_failed"
    assert result["attempts"] == 1
    assert result["error_type"] == "ValueError"

    print(
        "PASS: permanent failures are "
        "not retried."
    )


async def test_retry_exhaustion():
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

    assert orchestrator.calls == 3
    assert result["status"] == "scheduler_failed"
    assert result["attempts"] == 3
    assert (
        result["error_type"]
        == "ConnectionError"
    )

    print(
        "PASS: transient retries stop at "
        "the hard attempt limit."
    )


async def main():
    print("=" * 70)
    print(
        "AUTONOMOUS RETRY INTEGRATION TEST"
    )
    print()

    await test_transient_retry_success()
    await test_permanent_failure_no_retry()
    await test_retry_exhaustion()

    print()
    print("=" * 70)
    print(
        "ALL AUTONOMOUS RETRY "
        "INTEGRATION TESTS PASSED"
    )


if __name__ == "__main__":
    asyncio.run(main())
