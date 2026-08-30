"""Tests for autonomous production scheduler configuration."""

import os

from backend.services.orchestration.production_scheduler_config import (
    autonomous_production_enabled,
    autonomous_production_interval_seconds,
)


ENABLE_KEY = "JARVIS_AUTONOMOUS_PRODUCTION"
INTERVAL_KEY = "JARVIS_PRODUCTION_INTERVAL_SECONDS"


def clear_environment():
    os.environ.pop(
        ENABLE_KEY,
        None,
    )
    os.environ.pop(
        INTERVAL_KEY,
        None,
    )


def test_defaults():
    clear_environment()

    assert autonomous_production_enabled() is False

    assert (
        autonomous_production_interval_seconds()
        == 3600.0
    )

    print("=" * 70)
    print("SCHEDULER CONFIG DEFAULT TEST")
    print()
    print(
        "ENABLED:",
        autonomous_production_enabled(),
    )
    print(
        "INTERVAL:",
        autonomous_production_interval_seconds(),
    )
    print()
    print(
        "PASS: autonomous production is "
        "disabled by default."
    )


def test_explicit_enable():
    clear_environment()

    os.environ[ENABLE_KEY] = "true"
    os.environ[INTERVAL_KEY] = "7200"

    assert autonomous_production_enabled() is True

    assert (
        autonomous_production_interval_seconds()
        == 7200.0
    )

    print()
    print("=" * 70)
    print("SCHEDULER CONFIG ENABLE TEST")
    print()
    print(
        "ENABLED:",
        autonomous_production_enabled(),
    )
    print(
        "INTERVAL:",
        autonomous_production_interval_seconds(),
    )
    print()
    print(
        "PASS: autonomous production can "
        "be explicitly enabled."
    )


def test_invalid_values():
    clear_environment()

    os.environ[ENABLE_KEY] = "maybe"

    try:
        autonomous_production_enabled()
    except ValueError:
        pass
    else:
        raise AssertionError(
            "Invalid boolean was accepted."
        )

    clear_environment()

    os.environ[INTERVAL_KEY] = "0"

    try:
        autonomous_production_interval_seconds()
    except ValueError:
        pass
    else:
        raise AssertionError(
            "Invalid interval was accepted."
        )

    clear_environment()

    print()
    print("=" * 70)
    print("SCHEDULER CONFIG VALIDATION TEST")
    print()
    print(
        "PASS: invalid autonomy settings "
        "are rejected."
    )


def main():
    try:
        test_defaults()
        test_explicit_enable()
        test_invalid_values()

        print()
        print("=" * 70)
        print(
            "ALL SCHEDULER CONFIG TESTS PASSED"
        )

    finally:
        clear_environment()


if __name__ == "__main__":
    main()
