"""Tests for structured production failure classification."""

from backend.services.orchestration.failure_classification import (
    FailureCategory,
    classify_failure_category,
)


def main():
    retryable = [
        FailureCategory.TRANSIENT_PROVIDER_ERROR,
        FailureCategory.RATE_LIMITED,
        FailureCategory.SERVICE_UNAVAILABLE,
    ]

    permanent = [
        FailureCategory.INVALID_CONTENT,
        FailureCategory.CONFIGURATION_ERROR,
        FailureCategory.VALIDATION_ERROR,
        FailureCategory.UNKNOWN,
    ]

    for category in retryable:
        failure = classify_failure_category(
            category,
            detail="temporary failure",
        )

        assert failure.category == category
        assert failure.retryable is True

    for category in permanent:
        failure = classify_failure_category(
            category
        )

        assert failure.category == category
        assert failure.retryable is False

    string_failure = classify_failure_category(
        "RATE_LIMITED",
        detail="provider quota",
    )

    assert (
        string_failure.category
        == FailureCategory.RATE_LIMITED
    )
    assert string_failure.retryable is True
    assert (
        string_failure.detail
        == "provider quota"
    )

    unknown = classify_failure_category(
        "something_we_do_not_recognize"
    )

    assert (
        unknown.category
        == FailureCategory.UNKNOWN
    )
    assert unknown.retryable is False

    missing = classify_failure_category(
        None
    )

    assert (
        missing.category
        == FailureCategory.UNKNOWN
    )
    assert missing.retryable is False

    payload = string_failure.to_dict()

    assert payload == {
        "category": "rate_limited",
        "retryable": True,
        "detail": "provider quota",
    }

    print("=" * 70)
    print(
        "STRUCTURED FAILURE "
        "CLASSIFICATION TEST"
    )
    print()

    for category in retryable:
        print(
            category.value,
            "=> retryable",
        )

    for category in permanent:
        print(
            category.value,
            "=> permanent",
        )

    print()
    print(
        "UNKNOWN INPUT =>",
        unknown.to_dict(),
    )

    print()
    print(
        "PASS: known transient failures "
        "are retryable."
    )
    print(
        "PASS: permanent and unknown "
        "failures fail closed."
    )
    print(
        "PASS: failure classifications "
        "serialize safely."
    )

    print()
    print("=" * 70)
    print(
        "ALL STRUCTURED FAILURE "
        "CLASSIFICATION TESTS PASSED"
    )


if __name__ == "__main__":
    main()
