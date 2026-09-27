"""Persisted network kill switches; public publishing defaults OFF."""

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


class NetworkControl(Base):
    __tablename__ = "network_control"

    id: Mapped[str] = mapped_column(String(20), primary_key=True, default="global")
    production_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    accept_new_jobs: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    publishing_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    emergency_stop: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    min_free_bytes: Mapped[int] = mapped_column(default=5 * 1024**3, nullable=False)
