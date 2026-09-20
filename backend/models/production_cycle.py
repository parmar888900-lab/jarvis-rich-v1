"""Persistent production-cycle model."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Enum,
    Float,
    String,
    Text,
    func,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
)

from backend.database import Base


class ProductionCycleStatus(str, enum.Enum):
    STARTED = "started"
    COMPLETED = "completed"
    NO_ACTION = "no_action"
    FAILED = "failed"


class ProductionCycleRecord(Base):
    """Persisted record of one production orchestration cycle."""

    __tablename__ = "production_cycles"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )

    status: Mapped[ProductionCycleStatus] = mapped_column(
        Enum(
            ProductionCycleStatus,
            native_enum=False,
        ),
        nullable=False,
        default=ProductionCycleStatus.STARTED,
        index=True,
    )

    selected_topic: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    production_score: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    result: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    started_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )
