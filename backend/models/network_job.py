"""Durable Network V1 production jobs, preserving the full stage vocabulary."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Index, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


JOB_STATES = frozenset({
    "QUEUED", "RESEARCHING", "EVIDENCE_READY", "SCRIPTING", "SCRIPTED",
    "VISUAL_PLANNING", "MEDIA_RESOLVING", "MEDIA_READY", "NARRATING",
    "EDITING", "RENDERING", "QA", "REPAIR", "APPROVED",
    "WAITING_FOR_QUOTA", "WAITING_FOR_SCHEDULE", "UPLOADING", "SCHEDULED",
    "PUBLISHED", "ANALYTICS_PENDING", "COMPLETE", "FAILED",
    "HUMAN_ACTION_REQUIRED",
})


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


class NetworkJob(Base):
    __tablename__ = "network_jobs"
    __table_args__ = (Index("ix_network_job_channel_state", "channel_id", "state"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True,
                                    default=lambda: str(uuid4()))
    channel_id: Mapped[str] = mapped_column(String(36), ForeignKey("network_channels.id"),
                                            nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(180), nullable=False, unique=True)
    production_engine: Mapped[str] = mapped_column(String(64), nullable=False, default="rich_v1")
    state: Mapped[str] = mapped_column(String(48), nullable=False, default="QUEUED", index=True)
    attempt: Mapped[int] = mapped_column(nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(nullable=False, default=3)
    topic: Mapped[str | None] = mapped_column(String(500))
    topic_key: Mapped[str | None] = mapped_column(String(500), index=True)
    scheduler_decision: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    artifacts: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    lineage: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    last_result: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    failure_reason: Mapped[str | None] = mapped_column(Text)
    retry_after: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    worker_id: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc,
                                                 onupdate=now_utc)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class NetworkJobEvent(Base):
    __tablename__ = "network_job_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(String(36), ForeignKey("network_jobs.id"),
                                        nullable=False, index=True)
    from_state: Mapped[str | None] = mapped_column(String(48))
    to_state: Mapped[str] = mapped_column(String(48), nullable=False)
    attempt: Mapped[int] = mapped_column(nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
