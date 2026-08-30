"""Safety test for disabling autonomy during active production."""

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
        import asyncio

        self.calls += 1
        self.started.set()

        while not self.release.is_set():
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
            enable = client.post(
                "/production/autonomy/enable"
            )

            assert enable.status_code == 200
            assert enable.json()["enabled"] is True
            assert enable.json()["running"] is True

            def run_manual_cycle():
                production_response["response"] = (
                    client.post(
                        "/production/cycle"
                    )
                )

            worker = threading.Thread(
                target=run_manual_cycle
            )

            worker.start()

            assert fake.started.wait(
                timeout=5
            ), (
                "Manual production cycle did not "
                "start within timeout."
            )

            active_status = client.get(
                "/production/status"
            )

            assert active_status.status_code == 200

            active_body = active_status.json()

            assert (
                active_body["production"]["busy"]
                is True
            )

            disable = client.post(
                "/production/autonomy/disable"
            )

            assert disable.status_code == 200

            disable_body = disable.json()

            assert disable_body["enabled"] is False
            assert disable_body["running"] is False

            during_disable = client.get(
                "/production/status"
            )

            assert (
                during_disable.status_code
                == 200
            )

            during_body = during_disable.json()

            assert (
                during_body["production"]["busy"]
                is True
            )

            assert (
                during_body["scheduler"]["enabled"]
                is False
            )

            assert (
                during_body["scheduler"]["running"]
                is False
            )

            assert worker.is_alive()

            print("=" * 70)
            print(
                "AUTONOMY DISABLE SAFETY TEST"
            )
            print()
            print(
                "BUSY BEFORE DISABLE:",
                active_body["production"]["busy"],
            )
            print(
                "AUTONOMY ENABLED AFTER DISABLE:",
                during_body["scheduler"]["enabled"],
            )
            print(
                "SCHEDULER RUNNING AFTER DISABLE:",
                during_body["scheduler"]["running"],
            )
            print(
                "ACTIVE CYCLE STILL RUNNING:",
                worker.is_alive(),
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

            final_status = client.get(
                "/production/status"
            )

            assert final_status.status_code == 200

            final_body = final_status.json()

            assert (
                final_body["production"]["busy"]
                is False
            )

            assert fake.calls == 1

            print(
                "MANUAL CYCLE HTTP STATUS:",
                finished.status_code,
            )
            print(
                "BUSY AFTER COMPLETION:",
                final_body["production"]["busy"],
            )
            print(
                "ORCHESTRATOR CALLS:",
                fake.calls,
            )
            print()
            print(
                "PASS: disabling autonomy stops "
                "future scheduling without cancelling "
                "the active manual production cycle."
            )

    finally:
        fake.release.set()
        production.orchestrator = original

    print()
    print("=" * 70)
    print(
        "ALL AUTONOMY DISABLE SAFETY "
        "TESTS PASSED"
    )


if __name__ == "__main__":
    main()
