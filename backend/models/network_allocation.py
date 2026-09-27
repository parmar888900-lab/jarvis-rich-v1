"""Persistent daily production allocation rationale."""

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


class NetworkAllocation(Base):
    __tablename__ = "network_allocations"
    __table_args__ = (UniqueConstraint("channel_id", "local_date",
                                       name="uq_channel_local_allocation"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True,
                                    default=lambda: str(uuid4()))
    channel_id: Mapped[str] = mapped_column(String(36), ForeignKey("network_channels.id"),
                                            nullable=False, index=True)
    local_date: Mapped[str] = mapped_column(String(10), nullable=False)
    target: Mapped[int] = mapped_column(nullable=False)
    rationale: Mapped[dict] = mapped_column(JSON, nullable=False)
    selected_job_ids: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                   default=lambda: datetime.now(timezone.utc))
