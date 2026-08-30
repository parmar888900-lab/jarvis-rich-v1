"""Tests for autonomous production retry policy."""

from backend.services.orchestration.autonomous_retry import (
    AutonomousRetryPolicy,
)


def main():
    policy = AutonomousRetryPolicy(
        max_attempts=4,
        base_delay_seconds=2,
        multiplier=2,
        max_delay_seconds=5,
    )

    assert policy.is_retryable_exception(
        TimeoutError()
    )

    assert policy.is_retryable_exception(
        ConnectionError()
    )

    assert not policy.is_retryable_exception(
        ValueError()
    )

    assert not policy.is_retryable_exception(
        RuntimeError()
    )

    assert policy.delay_for_retry(1) == 2
    assert policy.delay_for_retry(2) == 4
    assert policy.delay_for_retry(3) == 5
    assert policy.delay_for_retry(4) == 5

    print("=" * 70)
    print("AUTONOMOUS RETRY POLICY TEST")
    print()
    print("MAX ATTEMPTS:", policy.max_attempts)
    print(
        "TIMEOUT RETRYABLE:",
        policy.is_retryable_exception(
            TimeoutError()
        ),
    )
    print(
        "CONNECTION RETRYABLE:",
        policy.is_retryable_exception(
            ConnectionError()
        ),
    )
    print(
        "VALUE ERROR RETRYABLE:",
        policy.is_retryable_exception(
            ValueError()
        ),
    )
    print(
        "BACKOFF:",
        [
            policy.delay_for_retry(n)
            for n in range(1, 5)
        ],
    )
    print()
    print(
        "PASS: retry policy distinguishes "
        "transient failures and caps "
        "exponential backoff."
    )

    invalid_cases = [
        {
            "max_attempts": 0,
        },
        {
            "base_delay_seconds": -1,
        },
        {
            "multiplier": 0.5,
        },
        {
            "max_delay_seconds": -1,
        },
    ]

    for kwargs in invalid_cases:
        try:
            AutonomousRetryPolicy(
                **kwargs
            )
        except ValueError:
            pass
        else:
            raise AssertionError(
                f"Expected ValueError for {kwargs}"
            )

    print(
        "PASS: invalid retry configurations "
        "are rejected."
    )

    print()
    print("=" * 70)
    print(
        "ALL AUTONOMOUS RETRY POLICY "
        "TESTS PASSED"
    )


if __name__ == "__main__":
    main()
