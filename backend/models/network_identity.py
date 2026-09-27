"""Network-wide content identity and lineage signals, without fabricated metadata."""

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


class NetworkContentIdentity(Base):
    __tablename__ = "network_content_identities"

    id: Mapped[str] = mapped_column(String(36), primary_key=True,
                                    default=lambda: str(uuid4()))
    job_id: Mapped[str] = mapped_column(String(36), ForeignKey("network_jobs.id"),
                                        nullable=False, unique=True)
    channel_id: Mapped[str] = mapped_column(String(36), ForeignKey("network_channels.id"),
                                            nullable=False, index=True)
    topic: Mapped[str] = mapped_column(Text, nullable=False)
    central_claim: Mapped[str | None] = mapped_column(Text)
    hook: Mapped[str | None] = mapped_column(Text)
    script: Mapped[str | None] = mapped_column(Text)
    narrative_structure: Mapped[str | None] = mapped_column(Text)
    source_ids: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    media_fingerprints: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    shot_sequence: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    narration_sha256: Mapped[str | None] = mapped_column(String(64))
    render_sha256: Mapped[str | None] = mapped_column(String(64), unique=True)
    title: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                   default=lambda: datetime.now(timezone.utc))
