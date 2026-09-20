"""Configuration for autonomous production scheduling."""

import os


DEFAULT_PRODUCTION_INTERVAL_SECONDS = 3600


def _read_bool(
    name: str,
    *,
    default: bool,
) -> bool:
    """Read a strict boolean environment variable."""

    raw_value = os.getenv(name)

    if raw_value is None:
        return default

    value = raw_value.strip().lower()

    if value in {
        "1",
        "true",
        "yes",
        "on",
    }:
        return True

    if value in {
        "0",
        "false",
        "no",
        "off",
    }:
        return False

    raise ValueError(
        f"{name} must be a boolean value."
    )


def _read_positive_float(
    name: str,
    *,
    default: float,
) -> float:
    """Read a positive numeric environment variable."""

    raw_value = os.getenv(name)

    if raw_value is None:
        return float(default)

    try:
        value = float(raw_value)
    except ValueError as exc:
        raise ValueError(
            f"{name} must be numeric."
        ) from exc

    if value <= 0:
        raise ValueError(
            f"{name} must be greater than zero."
        )

    return value


def autonomous_production_enabled() -> bool:
    """Return whether autonomous production is enabled."""

    return _read_bool(
        "JARVIS_AUTONOMOUS_PRODUCTION",
        default=False,
    )


def autonomous_production_interval_seconds() -> float:
    """Return the autonomous production interval."""

    return _read_positive_float(
        "JARVIS_PRODUCTION_INTERVAL_SECONDS",
        default=DEFAULT_PRODUCTION_INTERVAL_SECONDS,
    )
