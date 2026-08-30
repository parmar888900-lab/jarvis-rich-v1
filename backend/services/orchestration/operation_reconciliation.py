"""Provider reconciliation primitives for production side effects."""

from dataclasses import dataclass
from enum import Enum
from typing import Protocol


class ReconciliationStatus(str, Enum):
    """Outcome of checking a side effect with its provider."""

    CONFIRMED_COMPLETED = "confirmed_completed"
    CONFIRMED_NOT_FOUND = "confirmed_not_found"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ReconciliationResult:
    """Result returned by a provider reconciliation check."""

    status: ReconciliationStatus
    external_id: str | None = None
    detail: str | None = None

    @property
    def safe_to_retry(self) -> bool:
        return (
            self.status
            == ReconciliationStatus.CONFIRMED_NOT_FOUND
        )

    @property
    def confirmed_completed(self) -> bool:
        return (
            self.status
            == ReconciliationStatus.CONFIRMED_COMPLETED
        )


class OperationReconciler(Protocol):
    """Interface implemented by external provider reconcilers."""

    async def reconcile(
        self,
        *,
        operation_type: str,
        resource_id: str,
        idempotency_key: str,
    ) -> ReconciliationResult:
        """Determine whether an external side effect occurred."""
        ...
