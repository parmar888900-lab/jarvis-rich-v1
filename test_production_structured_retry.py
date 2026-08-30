"""Tests for autonomous retries driven by structured results."""

import asyncio

from backend.services.orchestration.autonomous_retry import (
    AutonomousRetryPolicy,
)
from backend.services.orchestration.production_scheduler import (
    ProductionScheduler,
)


class RetryableThenSuccessOrchestrator:
    def __init__(self):
        self.calls = 0

    async def run_cycle(self, cycle_id):
        self.calls += 1

        if self.calls == 1:
            return {
                "cycle_id": cycle_id,
                "status": "analysis_failed",
                "failure": {
                    "category": (
                        "transient_provider_error"
                    ),
                    "retryable": True,
                    "detail": "temporary provider failure",
                },
            }

        return {
            "cycle_id": cycle_id,
            "status": "success",
        }


class PermanentFailureOrchestrator:
    def __init__(self):
        self.calls = 0

    async def run_cycle(self, cycle_id):
        self.calls += 1

        return {
            "cycle_id": cycle_id,
            "status": "production_failed",
            "failure": {
                "category": "validation_error",
                "retryable": False,
                "detail": "content rejected",
            },
        }


class AlwaysRetryableOrchestrator:
    def __init__(self):
        self.calls = 0

    async def run_cycle(self, cycle_id):
        self.calls += 1

        return {
            "cycle_id": cycle_id,
            "status": "production_failed",
            "failure": {
                "category": "rate_limited",
                "retryable": True,
                "detail": "provider rate limit",
            },
        }


class NoActionOrchestrator:
    def __init__(self):
        self.calls = 0

    async def run_cycle(self, cycle_id):
        self.calls += 1

        return {
            "cycle_id": cycle_id,
            "status": "no_action",
            "reason": "no_production_ready_topic",
        }


async def test_retryable_result_then_success():
    orchestrator = (
        RetryableThenSuccessOrchestrator()
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

    assert orchestrator.calls == 2
    assert result["status"] == "success"

    print(
        "PASS: retryable pipeline failure "
        "retries and can recover."
    )


async def test_permanent_result_no_retry():
    orchestrator = (
        PermanentFailureOrchestrator()
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

    assert orchestrator.calls == 1
    assert (
        result["status"]
        == "production_failed"
    )

    assert (
        result["failure"]["retryable"]
        is False
    )

    print(
        "PASS: permanent pipeline failure "
        "is not retried."
    )


async def test_retryable_result_exhaustion():
    orchestrator = (
        AlwaysRetryableOrchestrator()
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
    assert (
        result["status"]
        == "production_failed"
    )

    assert (
        result["failure"]["category"]
        == "rate_limited"
    )

    print(
        "PASS: retryable pipeline failure "
        "stops at the hard attempt limit."
    )


async def test_no_action_never_retries():
    orchestrator = NoActionOrchestrator()

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
    assert result["status"] == "no_action"

    print(
        "PASS: no-action decisions "
        "are never retried."
    )


async def main():
    print("=" * 70)
    print(
        "STRUCTURED RESULT RETRY TEST"
    )
    print()

    await test_retryable_result_then_success()
    await test_permanent_result_no_retry()
    await test_retryable_result_exhaustion()
    await test_no_action_never_retries()

    print()
    print("=" * 70)
    print(
        "ALL STRUCTURED RESULT "
        "RETRY TESTS PASSED"
    )


if __name__ == "__main__":
    asyncio.run(main())

