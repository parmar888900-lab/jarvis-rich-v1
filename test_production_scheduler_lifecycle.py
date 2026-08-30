"""FastAPI lifecycle tests for production scheduler configuration."""

import os
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.app import app


ENABLE_KEY = "JARVIS_AUTONOMOUS_PRODUCTION"
INTERVAL_KEY = "JARVIS_PRODUCTION_INTERVAL_SECONDS"


class FakeOrchestrator:
    def __init__(self):
        self.calls = 0

    async def run_cycle(self, cycle_id):
        self.calls += 1

        return {
            "cycle_id": cycle_id,
            "status": "success",
        }


def clear_environment():
    os.environ.pop(
        ENABLE_KEY,
        None,
    )
    os.environ.pop(
        INTERVAL_KEY,
        None,
    )


def test_default_disabled():
    clear_environment()

    fake = FakeOrchestrator()

    with patch(
        "backend.routes.production.orchestrator",
        fake,
    ):
        with TestClient(app) as client:
            response = client.get("/")

            assert response.status_code == 200

            scheduler = (
                app.state.production_scheduler
            )

            assert scheduler.enabled is False
            assert scheduler.running is False
            assert fake.calls == 0

    assert scheduler.running is False

    print("=" * 70)
    print("LIFECYCLE DEFAULT-DISABLED TEST")
    print()
    print("ENABLED:", scheduler.enabled)
    print("RUNNING:", scheduler.running)
    print("PRODUCTION CALLS:", fake.calls)
    print()
    print(
        "PASS: default startup does not "
        "launch autonomous production."
    )


def test_explicit_enabled():
    clear_environment()

    os.environ[ENABLE_KEY] = "true"

    # Long interval prevents any actual scheduled
    # execution during this lifecycle test.
    os.environ[INTERVAL_KEY] = "3600"

    fake = FakeOrchestrator()

    with patch(
        "backend.routes.production.orchestrator",
        fake,
    ):
        with TestClient(app) as client:
            response = client.get("/")

            assert response.status_code == 200

            scheduler = (
                app.state.production_scheduler
            )

            assert scheduler.enabled is True
            assert scheduler.running is True
            assert fake.calls == 0

        assert scheduler.running is False

    clear_environment()

    print()
    print("=" * 70)
    print("LIFECYCLE EXPLICIT-ENABLE TEST")
    print()
    print("ENABLED:", scheduler.enabled)
    print(
        "RUNNING AFTER SHUTDOWN:",
        scheduler.running,
    )
    print("PRODUCTION CALLS:", fake.calls)
    print()
    print(
        "PASS: explicit enable starts the "
        "scheduler and shutdown stops it cleanly."
    )


def main():
    try:
        test_default_disabled()
        test_explicit_enabled()

        print()
        print("=" * 70)
        print(
            "ALL PRODUCTION SCHEDULER "
            "LIFECYCLE TESTS PASSED"
        )

    finally:
        clear_environment()


if __name__ == "__main__":
    main()
