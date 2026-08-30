"""FastAPI lifecycle test for the production scheduler."""

from fastapi.testclient import TestClient

from backend.app import app


def main():
    print("=" * 70)
    print("PRODUCTION SCHEDULER LIFECYCLE TEST")
    print()

    with TestClient(app) as client:
        response = client.get("/")

        assert response.status_code == 200

        scheduler = (
            app.state.production_scheduler
        )

        assert scheduler is not None
        assert scheduler.enabled is False
        assert scheduler.running is False

        print("ROOT STATUS:", response.status_code)
        print(
            "SCHEDULER ENABLED:",
            scheduler.enabled,
        )
        print(
            "SCHEDULER RUNNING:",
            scheduler.running,
        )

    assert scheduler.running is False

    print()
    print(
        "PASS: FastAPI creates the scheduler, "
        "keeps autonomous production disabled, "
        "and shuts down cleanly."
    )

    print()
    print("=" * 70)
    print(
        "PRODUCTION SCHEDULER LIFECYCLE TEST PASSED"
    )


if __name__ == "__main__":
    main()
