"""Command ORM model and Pydantic schemas for the Commander system."""

import enum
import uuid
from datetime import datetime

from pydantic import BaseModel, Field
from sqlalchemy import DateTime, Enum, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


class CommandPriority(str, enum.Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class CommandStatus(str, enum.Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    REJECTED = "rejected"


class CommandRecord(Base):
    """Persisted command log entry."""

    __tablename__ = "commands"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    timestamp: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    priority: Mapped[CommandPriority] = mapped_column(
        Enum(CommandPriority, native_enum=False), default=CommandPriority.NORMAL
    )
    agent: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    task: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[CommandStatus] = mapped_column(
        Enum(CommandStatus, native_enum=False), default=CommandStatus.PENDING
    )
    result: Mapped[str | None] = mapped_column(Text, nullable=True)


# --- Pydantic schemas ---


class CommandSubmitRequest(BaseModel):
    """Incoming POST /command body."""

    agent: str = Field(..., min_length=1, max_length=100, examples=["youtube"])
    task: str = Field(..., min_length=1, max_length=200, examples=["create_video"])
    priority: CommandPriority = Field(default=CommandPriority.NORMAL)


class CommandSubmitResponse(BaseModel):
    """Immediate response after command acceptance."""

    status: str = Field(..., examples=["accepted"])
    command_id: str


class CommandSchema(BaseModel):
    """Full command representation."""

    id: str
    timestamp: datetime
    priority: CommandPriority
    agent: str
    task: str
    status: CommandStatus
    result: str | None = None

    model_config = {"from_attributes": True}


class CommandErrorResponse(BaseModel):
    """Structured error payload."""

    error: str
    detail: str
    command_id: str | None = None
