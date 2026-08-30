"""HTTP tests for live production autonomy controls."""

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
        initial = client.get(
            "/production/status"
        )

        assert initial.status_code == 200

        initial_scheduler = (
            initial.json()["scheduler"]
        )

        assert initial_scheduler["enabled"] is False
        assert initial_scheduler["running"] is False

        first_enable = client.post(
            "/production/autonomy/enable"
        )

        assert first_enable.status_code == 200

        first_enable_body = (
            first_enable.json()
        )

        assert first_enable_body["enabled"] is True
        assert first_enable_body["running"] is True
        assert first_enable_body["changed"] is True

        second_enable = client.post(
            "/production/autonomy/enable"
        )

        assert second_enable.status_code == 200

        second_enable_body = (
            second_enable.json()
        )

        assert second_enable_body["enabled"] is True
        assert second_enable_body["running"] is True
        assert second_enable_body["changed"] is False

        enabled_status = client.get(
            "/production/status"
        ).json()["scheduler"]

        assert enabled_status["enabled"] is True
        assert enabled_status["running"] is True

        first_disable = client.post(
            "/production/autonomy/disable"
        )

        assert first_disable.status_code == 200

        first_disable_body = (
            first_disable.json()
        )

        assert first_disable_body["enabled"] is False
        assert first_disable_body["running"] is False
        assert first_disable_body["changed"] is True

        second_disable = client.post(
            "/production/autonomy/disable"
        )

        assert second_disable.status_code == 200

        second_disable_body = (
            second_disable.json()
        )

        assert second_disable_body["enabled"] is False
        assert second_disable_body["running"] is False
        assert second_disable_body["changed"] is False

        final_status = client.get(
            "/production/status"
        ).json()["scheduler"]

        assert final_status["enabled"] is False
        assert final_status["running"] is False

        print("=" * 70)
        print("LIVE AUTONOMY CONTROL TEST")
        print()
        print(
            "INITIAL:",
            initial_scheduler,
        )
        print(
            "FIRST ENABLE:",
            first_enable_body,
        )
        print(
            "SECOND ENABLE:",
            second_enable_body,
        )
        print(
            "FIRST DISABLE:",
            first_disable_body,
        )
        print(
            "SECOND DISABLE:",
            second_disable_body,
        )
        print()
        print(
            "PASS: autonomy can be enabled "
            "and disabled live with idempotent "
            "API controls."
        )

    clear_scheduler_env()

    print()
    print("=" * 70)
    print(
        "ALL LIVE AUTONOMY CONTROL "
        "TESTS PASSED"
    )


if __name__ == "__main__":
    main()
