"""Durable human-only blocker queue, separate from healthy work."""

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


class HumanAction(Base):
    __tablename__ = "human_actions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True,
                                    default=lambda: str(uuid4()))
    channel_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("network_channels.id"))
    job_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("network_jobs.id"))
    kind: Mapped[str] = mapped_column(String(80), nullable=False)
    what_happened: Mapped[str] = mapped_column(Text, nullable=False)
    why_automation_stopped: Mapped[str] = mapped_column(Text, nullable=False)
    required_user_action: Mapped[str] = mapped_column(Text, nullable=False)
    resumes_afterward: Mapped[str] = mapped_column(Text, nullable=False)
    state: Mapped[str] = mapped_column(String(16), default="OPEN", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                   default=lambda: datetime.now(timezone.utc))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
