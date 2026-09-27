"""Durable editorial channel identity; external account facts remain nullable."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


CHANNEL_STATES = frozenset({
    "PLANNED", "BRANDING_READY", "READY_FOR_HUMAN_CREATION", "CREATED",
    "AUTHORIZATION_REQUIRED", "STANDARD", "PHONE_VERIFIED", "HISTORY_BUILDING",
    "ADVANCED", "ACTIVE", "PAUSED", "DEGRADED", "RESTRICTED",
    "YPP_ELIGIBLE", "YPP_REVIEW", "MONETIZED", "HUMAN_ACTION_REQUIRED",
})


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class NetworkChannel(Base):
    __tablename__ = "network_channels"
    __table_args__ = (UniqueConstraint("editorial_identity", name="uq_network_editorial_identity"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True,
                                    default=lambda: str(uuid4()))
    youtube_channel_id: Mapped[str | None] = mapped_column(String(128), unique=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    handle: Mapped[str | None] = mapped_column(String(160), unique=True)
    niche: Mapped[str] = mapped_column(String(160), nullable=False)
    production_engine: Mapped[str] = mapped_column(String(64), nullable=False, default="rich_v1")
    editorial_identity: Mapped[str] = mapped_column(String(500), nullable=False)
    topic_universe: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    allowed_topics: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    blocked_topics: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    branding_profile: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    voice_profile: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    visual_profile: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    caption_profile: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    metadata_profile: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    timezone: Mapped[str] = mapped_column(String(80), nullable=False, default="UTC")
    posting_windows: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    max_daily_posts: Mapped[int] = mapped_column(nullable=False, default=4)
    lifecycle_state: Mapped[str] = mapped_column(String(48), nullable=False, default="PLANNED")
    authorization_state: Mapped[str | None] = mapped_column(String(80))
    oauth_state: Mapped[str | None] = mapped_column(String(80))
    youtube_capability_state: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    upload_capability: Mapped[str | None] = mapped_column(String(80))
    feature_eligibility: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    activation_state: Mapped[str | None] = mapped_column(String(80))
    policy_state: Mapped[str | None] = mapped_column(String(80))
    restriction_state: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    performance_state: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    monetization_state: Mapped[str | None] = mapped_column(String(80))
    degraded_reason: Mapped[str | None] = mapped_column(String(500))
    paused: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now,
                                                 onupdate=utc_now)
