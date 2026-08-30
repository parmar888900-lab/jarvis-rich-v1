"""Structured failure classification for production workflows."""

from dataclasses import dataclass
from enum import Enum


class FailureCategory(str, Enum):
    """Known production failure categories."""

    TRANSIENT_PROVIDER_ERROR = (
        "transient_provider_error"
    )
    RATE_LIMITED = "rate_limited"
    SERVICE_UNAVAILABLE = "service_unavailable"

    INVALID_CONTENT = "invalid_content"
    CONFIGURATION_ERROR = "configuration_error"
    VALIDATION_ERROR = "validation_error"

    UNKNOWN = "unknown"


RETRYABLE_FAILURE_CATEGORIES = frozenset(
    {
        FailureCategory.TRANSIENT_PROVIDER_ERROR,
        FailureCategory.RATE_LIMITED,
        FailureCategory.SERVICE_UNAVAILABLE,
    }
)


@dataclass(frozen=True)
class FailureClassification:
    """Normalized description of a workflow failure."""

    category: FailureCategory
    detail: str | None = None

    @property
    def retryable(self) -> bool:
        """Return whether autonomous execution may retry."""

        return (
            self.category
            in RETRYABLE_FAILURE_CATEGORIES
        )

    def to_dict(self) -> dict:
        """Return a JSON-safe representation."""

        return {
            "category": self.category.value,
            "retryable": self.retryable,
            "detail": self.detail,
        }


def classify_failure_category(
    value: str | FailureCategory | None,
    *,
    detail: str | None = None,
) -> FailureClassification:
    """Normalize a supplied failure category safely."""

    if isinstance(
        value,
        FailureCategory,
    ):
        category = value

    elif isinstance(value, str):
        try:
            category = FailureCategory(
                value.strip().lower()
            )
        except ValueError:
            category = FailureCategory.UNKNOWN

    else:
        category = FailureCategory.UNKNOWN

    return FailureClassification(
        category=category,
        detail=detail,
    )
