"""HTTP tests for production observability."""

import os

from fastapi.testclient import TestClient

from backend.app import app


def clear_scheduler_env():
    os.environ.pop(
        "JARVIS_AUTONOMOUS_PRODUCTION",
        None,
    )
    os.environ.pop(
        "JARVIS_PRODUCTION_INTERVAL_SECONDS",
        None,
    )


def main():
    clear_scheduler_env()

    with TestClient(app) as client:
        response = client.get(
            "/production/status"
        )

        assert response.status_code == 200

        body = response.json()

        assert "production" in body
        assert "scheduler" in body
        assert "latest_cycle" in body

        assert isinstance(
            body["production"]["busy"],
            bool,
        )

        scheduler = body["scheduler"]

        assert scheduler["available"] is True
        assert scheduler["enabled"] is False
        assert scheduler["running"] is False
        assert (
            scheduler["interval_seconds"]
            == 3600.0
        )

        latest = body["latest_cycle"]

        if latest is not None:
            assert "cycle_id" in latest
            assert "status" in latest
            assert "started_at" in latest
            assert "completed_at" in latest
            assert "selected_topic" in latest
            assert "production_score" in latest
            assert "result" in latest

        print("=" * 70)
        print("PRODUCTION STATUS ENDPOINT TEST")
        print()
        print(
            "HTTP STATUS:",
            response.status_code,
        )
        print(
            "BUSY:",
            body["production"]["busy"],
        )
        print(
            "SCHEDULER AVAILABLE:",
            scheduler["available"],
        )
        print(
            "SCHEDULER ENABLED:",
            scheduler["enabled"],
        )
        print(
            "SCHEDULER RUNNING:",
            scheduler["running"],
        )
        print(
            "INTERVAL:",
            scheduler["interval_seconds"],
        )

        if latest is None:
            print(
                "LATEST CYCLE:",
                "none",
            )
        else:
            print(
                "LATEST CYCLE:",
                latest["cycle_id"],
            )
            print(
                "LATEST STATUS:",
                latest["status"],
            )

        print()
        print(
            "PASS: production status exposes "
            "runtime, scheduler, and persisted "
            "cycle state."
        )

    clear_scheduler_env()

    print()
    print("=" * 70)
    print(
        "ALL PRODUCTION STATUS TESTS PASSED"
    )


if __name__ == "__main__":
    main()
