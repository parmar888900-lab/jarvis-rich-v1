"""Commander — central orchestrator for receiving, validating, routing, and logging commands."""

import json
import logging
import uuid
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import LOGS_DIR
from backend.models.command import (
    CommandPriority,
    CommandRecord,
    CommandSchema,
    CommandStatus,
    CommandSubmitRequest,
    CommandSubmitResponse,
)
from backend.services.agent_registry import AgentNotFoundError, AgentRegistry, TaskNotSupportedError, build_default_registry

# ---------------------------------------------------------------------------
# Logging setup — every command is logged to file and stdout
# ---------------------------------------------------------------------------

LOG_FILE = LOGS_DIR / "commander.log"


def _setup_commander_logger() -> logging.Logger:
    logger = logging.getLogger("jarvis.commander")
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = RotatingFileHandler(LOG_FILE, maxBytes=5_000_000, backupCount=5, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    return logger


logger = _setup_commander_logger()


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class CommandValidationError(Exception):
    """Raised when incoming command data fails validation."""

    def __init__(self, detail: str):
        self.detail = detail
        super().__init__(detail)


# ---------------------------------------------------------------------------
# Commander
# ---------------------------------------------------------------------------


class Commander:
    """Receives commands, logs them, validates, routes to agents, and returns responses."""

    def __init__(self, registry: AgentRegistry | None = None) -> None:
        self.registry = registry or build_default_registry()

    # -- public API ---------------------------------------------------------

    async def receive(
        self,
        db: AsyncSession,
        payload: CommandSubmitRequest,
    ) -> CommandSubmitResponse:
        """Full pipeline: validate → log → route → respond."""
        command_id = str(uuid.uuid4())

        try:
            self.validate(payload)
            record = await self.log_command(db, command_id, payload, CommandStatus.ACCEPTED)

            logger.info(
                "COMMAND RECEIVED | id=%s agent=%s task=%s priority=%s",
                command_id,
                payload.agent,
                payload.task,
                payload.priority.value,
            )

            record.status = CommandStatus.PROCESSING
            await db.flush()

            result = await self.route(
                payload.agent,
                payload.task,
                command_id,
                parameters=payload.parameters,
            )

            record.status = CommandStatus.COMPLETED
            record.result = json.dumps(result)
            await db.flush()

            logger.info(
                "COMMAND COMPLETED | id=%s agent=%s task=%s",
                command_id,
                payload.agent,
                payload.task,
            )

            return CommandSubmitResponse(status="accepted", command_id=command_id)

        except (CommandValidationError, AgentNotFoundError, TaskNotSupportedError) as exc:
            await self._reject(db, command_id, payload, exc)
            raise

        except Exception as exc:
            logger.exception("COMMAND FAILED | id=%s error=%s", command_id, exc)
            await self._fail(db, command_id, payload, exc)
            raise

    async def get_command(self, db: AsyncSession, command_id: str) -> CommandSchema | None:
        record = await db.get(CommandRecord, command_id)
        if record is None:
            return None
        return CommandSchema.model_validate(record)

    # -- pipeline steps -----------------------------------------------------

    def validate(self, payload: CommandSubmitRequest) -> None:
        """Validate agent name and task before routing."""
        agent = payload.agent.strip().lower()
        task = payload.task.strip()

        if not agent:
            raise CommandValidationError("Agent name cannot be empty")
        if not task:
            raise CommandValidationError("Task cannot be empty")

        reserved_parameters = {
            "task",
            "command_id",
        }

        conflicts = (
            reserved_parameters
            & payload.parameters.keys()
        )

        if conflicts:
            names = ", ".join(
                sorted(conflicts)
            )
            raise CommandValidationError(
                "Reserved command parameters "
                f"cannot be supplied: {names}"
            )

        handler = self.registry.get(agent)
        if not handler.supports_task(task):
            raise TaskNotSupportedError(agent, task, handler.supported_tasks)

    async def log_command(
        self,
        db: AsyncSession,
        command_id: str,
        payload: CommandSubmitRequest,
        status: CommandStatus,
    ) -> CommandRecord:
        """Persist command to database and write to log file."""
        record = CommandRecord(
            id=command_id,
            timestamp=datetime.now(timezone.utc),
            priority=payload.priority,
            agent=payload.agent.strip().lower(),
            task=payload.task.strip(),
            status=status,
        )
        db.add(record)
        await db.flush()

        logger.debug(
            "COMMAND LOGGED | id=%s status=%s agent=%s task=%s",
            command_id,
            status.value,
            record.agent,
            record.task,
        )
        return record

    async def route(
        self,
        agent: str,
        task: str,
        command_id: str,
        parameters: dict | None = None,
    ) -> dict:
        """Route command to the registered agent handler."""
        handler = self.registry.get(agent)
        logger.info("ROUTING | id=%s → agent=%s task=%s", command_id, agent, task)
        return await handler.execute(
            task=task,
            command_id=command_id,
            **(parameters or {}),
        )

    # -- error helpers ------------------------------------------------------

    async def _reject(
        self,
        db: AsyncSession,
        command_id: str,
        payload: CommandSubmitRequest,
        exc: Exception,
    ) -> None:
        logger.warning(
            "COMMAND REJECTED | id=%s agent=%s task=%s reason=%s",
            command_id,
            payload.agent,
            payload.task,
            exc,
        )
        record = CommandRecord(
            id=command_id,
            timestamp=datetime.now(timezone.utc),
            priority=payload.priority,
            agent=payload.agent.strip().lower(),
            task=payload.task.strip(),
            status=CommandStatus.REJECTED,
            result=str(exc),
        )
        db.add(record)
        await db.flush()

    async def _fail(
        self,
        db: AsyncSession,
        command_id: str,
        payload: CommandSubmitRequest,
        exc: Exception,
    ) -> None:
        record = CommandRecord(
            id=command_id,
            timestamp=datetime.now(timezone.utc),
            priority=payload.priority,
            agent=payload.agent.strip().lower(),
            task=payload.task.strip(),
            status=CommandStatus.FAILED,
            result=str(exc),
        )
        db.add(record)
        await db.flush()
