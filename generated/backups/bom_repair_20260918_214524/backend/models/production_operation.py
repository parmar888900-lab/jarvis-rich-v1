"""Persistent idempotent production operation model."""

from datetime import datetime
from enum import Enum

from sqlalchemy import (
    DateTime,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


class ProductionOperationStatus(str, Enum):
    """Lifecycle states for side-effecting operations."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    RECONCILIATION_REQUIRED = "reconciliation_required"
    FAILED = "failed"


class ProductionOperationRecord(Base):
    """Persistent record for one idempotent operation."""

    __tablename__ = "production_operations"

    __table_args__ = (
        UniqueConstraint(
            "idempotency_key",
            name=(
                "uq_production_operations_"
                "idempotency_key"
            ),
        ),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    idempotency_key: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )

    operation_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    resource_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=ProductionOperationStatus.PENDING.value,
    )

    result: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    retry_authorized: Mapped[bool] = mapped_column(
        nullable=False,
        default=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )
