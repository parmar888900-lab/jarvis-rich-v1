"""Production readiness gate regression tests."""

import asyncio

from backend.services.orchestration.production_scheduler import (
    ProductionScheduler,
)
from backend.services.runtime.capabilities import (
    Capability,
    RuntimeCapabilityReport,
)
from backend.services.runtime.production_gate import (
    evaluate_production_readiness,
)


class FakeOrchestrator:
    async def run_cycle(self):
        return {
            "status": "success"
        }


def report(
    *,
    ready: bool,
) -> RuntimeCapabilityReport:

    return RuntimeCapabilityReport(
        capabilities=(
            Capability(
                name="test_dependency",
                available=ready,
                required_for_production=True,
                detail=(
                    "available"
                    if ready
                    else "missing"
                ),
            ),
        )
    )


def test_autonomy_off_does_not_start():
    decision = evaluate_production_readiness(
        autonomous_requested=False,
        report=report(
            ready=True
        ),
    )

    assert (
        decision.production_ready
        is True
    )

    assert (
        decision.scheduler_enabled
        is False
    )

    assert (
        decision.blocked
        is False
    )


def test_autonomy_on_ready_starts():
    decision = evaluate_production_readiness(
        autonomous_requested=True,
        report=report(
            ready=True
        ),
    )

    assert (
        decision.production_ready
        is True
    )

    assert (
        decision.scheduler_enabled
        is True
    )

    assert (
        decision.blocked
        is False
    )


def test_autonomy_on_missing_dependency_fails_closed():
    decision = evaluate_production_readiness(
        autonomous_requested=True,
        report=report(
            ready=False
        ),
    )

    assert (
        decision.production_ready
        is False
    )

    assert (
        decision.scheduler_enabled
        is False
    )

    assert (
        decision.blocked
        is True
    )

    assert (
        decision.missing_required
        == (
            "test_dependency",
        )
    )


async def test_scheduler_start_is_blocked():
    scheduler = ProductionScheduler(
        FakeOrchestrator(),
        interval_seconds=3600,
        enabled=True,
        production_allowed=False,
    )

    assert scheduler.enabled is False

    assert scheduler.start() is False

    assert scheduler.running is False

    await scheduler.stop()


async def test_manual_enable_cannot_bypass_gate():
    scheduler = ProductionScheduler(
        FakeOrchestrator(),
        interval_seconds=3600,
        enabled=False,
        production_allowed=False,
    )

    assert scheduler.enable() is False

    assert scheduler.enabled is False

    assert scheduler.running is False

    await scheduler.stop()


async def test_ready_scheduler_preserves_enable_behavior():
    scheduler = ProductionScheduler(
        FakeOrchestrator(),
        interval_seconds=3600,
        enabled=False,
        production_allowed=True,
    )

    assert scheduler.enable() is True

    assert scheduler.enabled is True

    assert scheduler.running is True

    await scheduler.stop()


def main():

    test_autonomy_off_does_not_start()

    print(
        "PASS: autonomy OFF remains disabled."
    )

    test_autonomy_on_ready_starts()

    print(
        "PASS: ready runtime permits autonomous production."
    )

    test_autonomy_on_missing_dependency_fails_closed()

    print(
        "PASS: missing production capability fails closed."
    )

    asyncio.run(
        test_scheduler_start_is_blocked()
    )

    print(
        "PASS: scheduler start cannot bypass readiness gate."
    )

    asyncio.run(
        test_manual_enable_cannot_bypass_gate()
    )

    print(
        "PASS: manual enable cannot bypass readiness gate."
    )

    asyncio.run(
        test_ready_scheduler_preserves_enable_behavior()
    )

    print(
        "PASS: ready scheduler retains normal enable behavior."
    )

    print()

    print(
        "PASS: production readiness gate regression suite complete."
    )


if __name__ == "__main__":
    main()
