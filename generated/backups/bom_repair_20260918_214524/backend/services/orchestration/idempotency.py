"""Idempotency primitives for side-effecting production operations."""

from dataclasses import dataclass
from enum import Enum
import hashlib


class OperationType(str, Enum):
    """Side-effecting production operation types."""

    UPLOAD_VIDEO = "upload_video"
    PUBLISH_VIDEO = "publish_video"


@dataclass(frozen=True)
class IdempotencyKey:
    """Stable identity for one side-effecting operation."""

    operation_type: OperationType
    resource_id: str

    def __post_init__(self) -> None:
        if not self.resource_id.strip():
            raise ValueError(
                "resource_id cannot be empty."
            )

    @property
    def value(self) -> str:
        """Return a deterministic compact operation key."""

        source = (
            f"{self.operation_type.value}:"
            f"{self.resource_id.strip()}"
        )

        digest = hashlib.sha256(
            source.encode("utf-8")
        ).hexdigest()

        return (
            f"{self.operation_type.value}:"
            f"{digest}"
        )


def build_idempotency_key(
    operation_type: OperationType,
    resource_id: str,
) -> str:
    """Build a stable key for a production side effect."""

    return IdempotencyKey(
        operation_type=operation_type,
        resource_id=resource_id,
    ).value
