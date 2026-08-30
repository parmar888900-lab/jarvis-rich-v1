"""Tests for the shared production runner."""

import asyncio

from backend.services.orchestration.production_runner import (
    ProductionCycleBusyError,
    ProductionRunner,
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


async def test_success():
    lock = asyncio.Lock()
    fake = FakeOrchestrator()

    runner = ProductionRunner(
        fake,
        lock=lock,
        cycle_id_factory=lambda: "test-cycle",
    )

    result = await runner.run_cycle()

    assert result == {
        "cycle_id": "test-cycle",
        "status": "success",
    }

    assert fake.calls == [
        "test-cycle"
    ]

    assert lock.locked() is False

    print("=" * 70)
    print("PRODUCTION RUNNER SUCCESS TEST")
    print()
    print("STATUS:", result["status"])
    print("CYCLE ID:", result["cycle_id"])
    print("LOCKED AFTER RUN:", lock.locked())
    print()
    print(
        "PASS: runner generates one cycle "
        "through the shared execution gate."
    )


async def test_busy():
    lock = asyncio.Lock()
    fake = FakeOrchestrator()

    runner = ProductionRunner(
        fake,
        lock=lock,
    )

    await lock.acquire()

    try:
        try:
            await runner.run_cycle()

        except ProductionCycleBusyError:
            pass

        else:
            raise AssertionError(
                "Busy production runner did not reject."
            )

        assert fake.calls == []

        print()
        print("=" * 70)
        print("PRODUCTION RUNNER BUSY TEST")
        print()
        print("ORCHESTRATOR CALLS:", len(fake.calls))
        print()
        print(
            "PASS: busy runner rejects without "
            "starting another production cycle."
        )

    finally:
        lock.release()


async def test_failure_releases_lock():
    class FailingOrchestrator:
        async def run_cycle(self, cycle_id):
            raise RuntimeError(
                "Fake production failure"
            )

    lock = asyncio.Lock()

    runner = ProductionRunner(
        FailingOrchestrator(),
        lock=lock,
        cycle_id_factory=lambda: "failure-cycle",
    )

    try:
        await runner.run_cycle()

    except RuntimeError as exc:
        assert str(exc) == (
            "Fake production failure"
        )

    else:
        raise AssertionError(
            "Production failure was not propagated."
        )

    assert lock.locked() is False

    print()
    print("=" * 70)
    print("PRODUCTION RUNNER FAILURE TEST")
    print()
    print(
        "LOCKED AFTER FAILURE:",
        lock.locked(),
    )
    print()
    print(
        "PASS: production failure propagates "
        "and the shared lock is released."
    )


async def test_sequential_reuse():
    lock = asyncio.Lock()
    fake = FakeOrchestrator()

    ids = iter(
        [
            "cycle-one",
            "cycle-two",
        ]
    )

    runner = ProductionRunner(
        fake,
        lock=lock,
        cycle_id_factory=lambda: next(ids),
    )

    first = await runner.run_cycle()
    second = await runner.run_cycle()

    assert first["cycle_id"] == "cycle-one"
    assert second["cycle_id"] == "cycle-two"

    assert fake.calls == [
        "cycle-one",
        "cycle-two",
    ]

    assert lock.locked() is False

    print()
    print("=" * 70)
    print("PRODUCTION RUNNER REUSE TEST")
    print()
    print("CALLS:", len(fake.calls))
    print("LOCKED AFTER RUNS:", lock.locked())
    print()
    print(
        "PASS: runner can execute sequential "
        "production cycles."
    )


async def main():
    await test_success()
    await test_busy()
    await test_failure_releases_lock()
    await test_sequential_reuse()

    print()
    print("=" * 70)
    print(
        "ALL PRODUCTION RUNNER TESTS PASSED"
    )


if __name__ == "__main__":
    asyncio.run(main())
