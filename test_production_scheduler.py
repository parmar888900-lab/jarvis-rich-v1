"""Tests for the autonomous production scheduler."""

import asyncio

from backend.services.orchestration.production_runtime import (
    production_lock,
)
from backend.services.orchestration.production_scheduler import (
    ProductionScheduler,
)


class FakeOrchestrator:
    def __init__(self):
        self.calls = []

    async def run_cycle(self, cycle_id):
        self.calls.append(cycle_id)

        return {
            "cycle_id": cycle_id,
            "status": "success",
        }


async def test_run_once_success():
    fake = FakeOrchestrator()

    scheduler = ProductionScheduler(
        fake,
        interval_seconds=60,
        enabled=True,
    )

    result = await scheduler.run_once()

    assert result["status"] == "success"
    assert len(fake.calls) == 1
    assert result["cycle_id"] == fake.calls[0]
    assert not production_lock.locked()

    print("=" * 70)
    print("SCHEDULER RUN-ONCE SUCCESS TEST")
    print()
    print("STATUS:", result["status"])
    print("CALLS:", len(fake.calls))
    print(
        "LOCKED AFTER RUN:",
        production_lock.locked(),
    )
    print()
    print(
        "PASS: scheduler executes one "
        "production cycle and releases the lock."
    )


async def test_busy_skip():
    fake = FakeOrchestrator()

    scheduler = ProductionScheduler(
        fake,
        interval_seconds=60,
        enabled=True,
    )

    await production_lock.acquire()

    try:
        result = await scheduler.run_once()

        assert result == {
            "status": "skipped",
            "reason": "production_busy",
            "attempts": 1,
        }

        assert fake.calls == []

        print()
        print("=" * 70)
        print("SCHEDULER BUSY-SKIP TEST")
        print()
        print("STATUS:", result["status"])
        print("REASON:", result["reason"])
        print("ORCHESTRATOR CALLS:", len(fake.calls))
        print()
        print(
            "PASS: scheduler skips a tick "
            "when production is already busy."
        )

    finally:
        production_lock.release()


async def test_failure_contained():
    class FailingOrchestrator:
        def __init__(self):
            self.calls = 0

        async def run_cycle(self, cycle_id):
            self.calls += 1

            raise RuntimeError(
                "Fake scheduled failure"
            )

    fake = FailingOrchestrator()

    scheduler = ProductionScheduler(
        fake,
        interval_seconds=60,
        enabled=True,
    )

    result = await scheduler.run_once()

    assert result["status"] == (
        "scheduler_failed"
    )

    assert result["reason"] == (
        "production_cycle_failed"
    )

    assert fake.calls == 1
    assert not production_lock.locked()

    print()
    print("=" * 70)
    print("SCHEDULER FAILURE-CONTAINMENT TEST")
    print()
    print("STATUS:", result["status"])
    print("CALLS:", fake.calls)
    print(
        "LOCKED AFTER FAILURE:",
        production_lock.locked(),
    )
    print()
    print(
        "PASS: production exceptions are "
        "contained and the lock is released."
    )


async def test_disabled_start():
    fake = FakeOrchestrator()

    scheduler = ProductionScheduler(
        fake,
        interval_seconds=60,
        enabled=False,
    )

    started = scheduler.start()

    assert started is False
    assert scheduler.running is False
    assert fake.calls == []

    print()
    print("=" * 70)
    print("SCHEDULER DISABLED TEST")
    print()
    print("STARTED:", started)
    print("RUNNING:", scheduler.running)
    print()
    print(
        "PASS: disabled scheduler does "
        "not create a background task."
    )


async def test_periodic_start_stop():
    fake = FakeOrchestrator()

    scheduler = ProductionScheduler(
        fake,
        interval_seconds=0.05,
        enabled=True,
    )

    started = scheduler.start()

    assert started is True
    assert scheduler.running is True

    duplicate_start = scheduler.start()

    assert duplicate_start is False

    await asyncio.sleep(
        0.13
    )

    stopped = await scheduler.stop()

    assert stopped is True
    assert scheduler.running is False

    assert len(fake.calls) >= 2
    assert not production_lock.locked()

    calls_after_stop = len(fake.calls)

    await asyncio.sleep(
        0.08
    )

    assert len(fake.calls) == calls_after_stop

    print()
    print("=" * 70)
    print("SCHEDULER START-STOP TEST")
    print()
    print("PRODUCTION CALLS:", len(fake.calls))
    print("RUNNING AFTER STOP:", scheduler.running)
    print()
    print(
        "PASS: scheduler runs periodically, "
        "rejects duplicate start, and stops cleanly."
    )


async def test_invalid_interval():
    try:
        ProductionScheduler(
            FakeOrchestrator(),
            interval_seconds=0,
        )
    except ValueError as exc:
        assert (
            "greater than zero"
            in str(exc)
        )
    else:
        raise AssertionError(
            "Zero scheduler interval accepted."
        )

    print()
    print("=" * 70)
    print("SCHEDULER INTERVAL VALIDATION TEST")
    print()
    print(
        "PASS: invalid scheduler intervals "
        "are rejected."
    )


async def main():
    await test_run_once_success()
    await test_busy_skip()
    await test_failure_contained()
    await test_disabled_start()
    await test_periodic_start_stop()
    await test_invalid_interval()

    print()
    print("=" * 70)
    print(
        "ALL PRODUCTION SCHEDULER TESTS PASSED"
    )


if __name__ == "__main__":
    asyncio.run(main())
