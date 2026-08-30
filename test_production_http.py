"""HTTP tests for the production-cycle endpoint."""

import asyncio
import threading

from fastapi.testclient import TestClient

from backend.app import app
from backend.routes import production
from backend.services.orchestration.production_runtime import (
    production_lock,
)


class FakeProductionOrchestrator:
    def __init__(self):
        self.calls = []

    async def run_cycle(self, cycle_id):
        self.calls.append(cycle_id)

        return {
            "cycle_id": cycle_id,
            "status": "success",
            "selected_trend": {
                "title": "HTTP production test trend",
                "production_selection": {
                    "eligible": True,
                    "selected": True,
                    "production_score": 88.5,
                },
            },
            "production": {
                "status": "success",
                "production_package": {
                    "video_path": "generated/http_test.mp4",
                },
            },
        }


def test_production_cycle_http():
    fake = FakeProductionOrchestrator()

    original = production.orchestrator
    production.orchestrator = fake

    try:
        with TestClient(app) as client:
            response = client.post(
                "/production/cycle"
            )

        assert response.status_code == 200

        data = response.json()

        assert data["status"] == "success"
        assert len(fake.calls) == 1

        cycle_id = fake.calls[0]

        assert isinstance(cycle_id, str)
        assert cycle_id
        assert data["cycle_id"] == cycle_id

        print("=" * 70)
        print("PRODUCTION HTTP SUCCESS TEST")
        print()
        print("HTTP STATUS:", response.status_code)
        print("CYCLE STATUS:", data["status"])
        print()
        print(
            "PASS: production endpoint runs "
            "the orchestrator once."
        )

    finally:
        production.orchestrator = original


def test_production_cycle_http_failure():
    class FailingProductionOrchestrator:
        async def run_cycle(self, cycle_id):
            raise RuntimeError(
                "Fake orchestrator crash"
            )

    original = production.orchestrator
    production.orchestrator = (
        FailingProductionOrchestrator()
    )

    try:
        with TestClient(app) as client:
            response = client.post(
                "/production/cycle"
            )

        assert response.status_code == 500

        data = response.json()

        assert (
            data["detail"]["error"]
            == "production_cycle_failed"
        )

        assert not production_lock.locked()

        print()
        print("=" * 70)
        print("PRODUCTION HTTP FAILURE TEST")
        print()
        print("HTTP STATUS:", response.status_code)
        print(
            "LOCKED AFTER FAILURE:",
            production_lock.locked(),
        )
        print()
        print(
            "PASS: exception becomes HTTP 500 "
            "and the production lock is released."
        )

    finally:
        production.orchestrator = original


def test_production_cycle_concurrency():
    started = threading.Event()
    release = threading.Event()

    class BlockingProductionOrchestrator:
        def __init__(self):
            self.calls = []

        async def run_cycle(
            self,
            cycle_id,
        ):
            self.calls.append(cycle_id)

            started.set()

            await asyncio.to_thread(
                release.wait
            )

            return {
                "cycle_id": cycle_id,
                "status": "success",
            }

    fake = BlockingProductionOrchestrator()

    original = production.orchestrator
    production.orchestrator = fake

    first_result = {}

    def run_first_request():
        with TestClient(app) as client:
            first_result["response"] = (
                client.post(
                    "/production/cycle"
                )
            )

    thread = threading.Thread(
        target=run_first_request
    )

    try:
        thread.start()

        assert started.wait(
            timeout=10
        ), (
            "First production request "
            "did not start."
        )

        assert production_lock.locked()

        with TestClient(app) as client:
            second_response = client.post(
                "/production/cycle"
            )

        assert (
            second_response.status_code
            == 409
        )

        data = second_response.json()

        assert (
            data["detail"]["error"]
            == "production_cycle_busy"
        )

        assert len(fake.calls) == 1

        release.set()

        thread.join(
            timeout=10
        )

        assert not thread.is_alive()

        first_response = (
            first_result["response"]
        )

        assert (
            first_response.status_code
            == 200
        )

        assert not production_lock.locked()

        print()
        print("=" * 70)
        print("PRODUCTION CONCURRENCY TEST")
        print()
        print(
            "SECOND REQUEST STATUS:",
            second_response.status_code,
        )
        print(
            "ORCHESTRATOR CALLS:",
            len(fake.calls),
        )
        print(
            "LOCKED AFTER COMPLETION:",
            production_lock.locked(),
        )
        print()
        print(
            "PASS: concurrent production "
            "request is rejected with HTTP 409 "
            "without starting a second cycle."
        )

    finally:
        release.set()

        if thread.is_alive():
            thread.join(
                timeout=10
            )

        production.orchestrator = original


def test_lock_reusable_after_completion():
    fake = FakeProductionOrchestrator()

    original = production.orchestrator
    production.orchestrator = fake

    try:
        with TestClient(app) as client:
            first = client.post(
                "/production/cycle"
            )

            second = client.post(
                "/production/cycle"
            )

        assert first.status_code == 200
        assert second.status_code == 200
        assert len(fake.calls) == 2
        assert not production_lock.locked()

        print()
        print("=" * 70)
        print("LOCK REUSE TEST")
        print()
        print(
            "FIRST STATUS:",
            first.status_code,
        )
        print(
            "SECOND STATUS:",
            second.status_code,
        )
        print()
        print(
            "PASS: sequential production "
            "cycles can run after the lock "
            "is released."
        )

    finally:
        production.orchestrator = original


def main():
    test_production_cycle_http()
    test_production_cycle_http_failure()
    test_production_cycle_concurrency()
    test_lock_reusable_after_completion()


if __name__ == "__main__":
    main()

