"""HTTP tests for the production-cycle endpoint."""

from fastapi.testclient import TestClient

from backend.app import app
from backend.routes import production


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

        assert (
            data["selected_trend"]["title"]
            == "HTTP production test trend"
        )

        assert (
            data["production"]
            ["production_package"]
            ["video_path"]
            == "generated/http_test.mp4"
        )

        print()
        print("=" * 70)
        print("PRODUCTION HTTP SUCCESS TEST")
        print()
        print("HTTP STATUS:", response.status_code)
        print("CYCLE STATUS:", data["status"])
        print("ORCHESTRATOR CALLS:", len(fake.calls))
        print("CYCLE ID:", cycle_id)
        print()
        print(
            "PASS: POST /production/cycle "
            "calls the orchestrator exactly once "
            "without running the real production pipeline."
        )

    finally:
        production.orchestrator = original


if __name__ == "__main__":
    test_production_cycle_http()

def test_production_cycle_http_failure():
    class FailingProductionOrchestrator:
        async def run_cycle(self, cycle_id):
            raise RuntimeError("Fake orchestrator crash")

    fake = FailingProductionOrchestrator()

    original = production.orchestrator
    production.orchestrator = fake

    try:
        with TestClient(app) as client:
            response = client.post(
                "/production/cycle"
            )

        assert response.status_code == 500

        data = response.json()

        assert data["detail"]["error"] == (
            "production_cycle_failed"
        )

        assert data["detail"]["detail"] == (
            "Production cycle failed"
        )

        print()
        print("=" * 70)
        print("PRODUCTION HTTP FAILURE TEST")
        print()
        print("HTTP STATUS:", response.status_code)
        print(
            "ERROR:",
            data["detail"]["error"],
        )
        print()
        print(
            "PASS: orchestrator exceptions become "
            "controlled HTTP 500 responses."
        )

    finally:
        production.orchestrator = original


if __name__ == "__main__":
    test_production_cycle_http_failure()
