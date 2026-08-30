"""Tests for production operation reconciliation primitives."""

from backend.services.orchestration.operation_reconciliation import (
    ReconciliationResult,
    ReconciliationStatus,
)


def main():
    print("=" * 70)
    print("OPERATION RECONCILIATION PRIMITIVE TEST")
    print()

    completed = ReconciliationResult(
        status=(
            ReconciliationStatus
            .CONFIRMED_COMPLETED
        ),
        external_id="youtube-123",
    )

    assert completed.confirmed_completed is True
    assert completed.safe_to_retry is False

    print(
        "PASS: confirmed external completion "
        "is never marked retryable."
    )

    missing = ReconciliationResult(
        status=(
            ReconciliationStatus
            .CONFIRMED_NOT_FOUND
        ),
    )

    assert missing.confirmed_completed is False
    assert missing.safe_to_retry is True

    print(
        "PASS: confirmed absence may be "
        "considered safe to retry."
    )

    unknown = ReconciliationResult(
        status=ReconciliationStatus.UNKNOWN,
        detail="provider check unavailable",
    )

    assert unknown.confirmed_completed is False
    assert unknown.safe_to_retry is False

    print(
        "PASS: uncertain provider state "
        "fails closed."
    )

    print()
    print("=" * 70)
    print(
        "ALL OPERATION RECONCILIATION "
        "PRIMITIVE TESTS PASSED"
    )


if __name__ == "__main__":
    main()
