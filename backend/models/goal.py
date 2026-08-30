"""Persistent goal model for the Jarvis Target/Goal Engine."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Enum,
    Float,
    String,
    func,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
)

from backend.database import Base


class GoalPeriod(str, enum.Enum):
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    CUSTOM = "custom"


class GoalStatus(str, enum.Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    PAUSED = "paused"
    FAILED = "failed"


class GoalRecord(Base):
    """Persisted performance target."""

    __tablename__ = "goals"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )

    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    metric: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )

    target_value: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    starting_value: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )

    current_value: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )

    period: Mapped[GoalPeriod] = mapped_column(
        Enum(
            GoalPeriod,
            native_enum=False,
        ),
        nullable=False,
        default=GoalPeriod.CUSTOM,
    )

    start_date: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
    )

    deadline: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
    )

    status: Mapped[GoalStatus] = mapped_column(
        Enum(
            GoalStatus,
            native_enum=False,
        ),
        nullable=False,
        default=GoalStatus.ACTIVE,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
    )
