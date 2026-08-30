"""Runtime-busy observability test."""

import threading

from fastapi.testclient import TestClient

from backend.app import app
from backend.routes import production


class BlockingOrchestrator:
    def __init__(self):
        self.started = threading.Event()
        self.release = threading.Event()
        self.calls = 0

    async def run_cycle(self, cycle_id):
        self.calls += 1

        self.started.set()

        while not self.release.is_set():
            import asyncio
            await asyncio.sleep(0.01)

        return {
            "cycle_id": cycle_id,
            "status": "success",
        }


def main():
    fake = BlockingOrchestrator()

    original = production.orchestrator
    production.orchestrator = fake

    production_response = {}

    try:
        with TestClient(app) as client:

            def run_cycle():
                production_response["response"] = (
                    client.post(
                        "/production/cycle"
                    )
                )

            worker = threading.Thread(
                target=run_cycle
            )

            worker.start()

            assert fake.started.wait(
                timeout=5
            ), (
                "Production cycle did not start "
                "within timeout."
            )

            status_response = client.get(
                "/production/status"
            )

            assert (
                status_response.status_code
                == 200
            )

            body = status_response.json()

            assert (
                body["production"]["busy"]
                is True
            )

            assert fake.calls == 1

            print("=" * 70)
            print(
                "PRODUCTION BUSY STATUS TEST"
            )
            print()
            print(
                "STATUS HTTP:",
                status_response.status_code,
            )
            print(
                "BUSY DURING PRODUCTION:",
                body["production"]["busy"],
            )
            print(
                "ORCHESTRATOR CALLS:",
                fake.calls,
            )

            fake.release.set()

            worker.join(
                timeout=5
            )

            assert not worker.is_alive()

            finished = (
                production_response["response"]
            )

            assert finished.status_code == 200

            after = client.get(
                "/production/status"
            )

            assert after.status_code == 200
            assert (
                after.json()["production"]["busy"]
                is False
            )

            print(
                "BUSY AFTER COMPLETION:",
                after.json()[
                    "production"
                ]["busy"],
            )
            print()
            print(
                "PASS: status endpoint reflects "
                "the real production execution lock."
            )

    finally:
        fake.release.set()
        production.orchestrator = original

    print()
    print("=" * 70)
    print(
        "ALL PRODUCTION BUSY STATUS "
        "TESTS PASSED"
    )


if __name__ == "__main__":
    main()
