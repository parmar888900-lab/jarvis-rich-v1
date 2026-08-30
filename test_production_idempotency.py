"""Tests for production operation idempotency keys."""

from backend.services.orchestration.idempotency import (
    IdempotencyKey,
    OperationType,
    build_idempotency_key,
)


def main():
    first = build_idempotency_key(
        OperationType.UPLOAD_VIDEO,
        "video-123",
    )

    second = build_idempotency_key(
        OperationType.UPLOAD_VIDEO,
        "video-123",
    )

    assert first == second

    different_resource = (
        build_idempotency_key(
            OperationType.UPLOAD_VIDEO,
            "video-456",
        )
    )

    assert first != different_resource

    different_operation = (
        build_idempotency_key(
            OperationType.PUBLISH_VIDEO,
            "video-123",
        )
    )

    assert first != different_operation

    whitespace_normalized = (
        build_idempotency_key(
            OperationType.UPLOAD_VIDEO,
            "  video-123  ",
        )
    )

    assert first == whitespace_normalized

    try:
        IdempotencyKey(
            operation_type=(
                OperationType.UPLOAD_VIDEO
            ),
            resource_id="   ",
        )
    except ValueError:
        pass
    else:
        raise AssertionError(
            "Empty resource ID was accepted."
        )

    assert first.startswith(
        "upload_video:"
    )

    print("=" * 70)
    print(
        "PRODUCTION IDEMPOTENCY "
        "KEY TEST"
    )
    print()

    print(
        "PASS: identical operations "
        "produce identical keys."
    )
    print(
        "PASS: different resources "
        "produce different keys."
    )
    print(
        "PASS: different operation types "
        "produce different keys."
    )
    print(
        "PASS: resource IDs are normalized."
    )
    print(
        "PASS: empty resource IDs "
        "are rejected."
    )

    print()
    print(
        "Example key:",
        first,
    )

    print()
    print("=" * 70)
    print(
        "ALL PRODUCTION IDEMPOTENCY "
        "KEY TESTS PASSED"
    )


if __name__ == "__main__":
    main()
