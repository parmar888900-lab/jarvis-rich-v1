"""Persistent YouTube video performance snapshots."""

from datetime import datetime

from sqlalchemy import (
    DateTime,
    Index,
    Integer,
    String,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
)

from backend.database import Base


class YoutubePerformanceSnapshotRecord(Base):
    """Immutable observation of one YouTube video's statistics."""

    __tablename__ = "youtube_performance_snapshots"

    __table_args__ = (
        Index(
            "ix_youtube_performance_video_captured",
            "video_id",
            "captured_at",
        ),
        Index(
            "ix_youtube_performance_channel_captured",
            "channel_id",
            "captured_at",
        ),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    video_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )

    channel_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )

    title: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        default="",
    )

    privacy_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="",
    )

    published_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    captured_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        index=True,
    )

    views: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    likes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    comments: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
