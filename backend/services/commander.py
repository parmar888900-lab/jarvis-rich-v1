"""Commander — central orchestrator for receiving, validating, routing, and logging commands."""

import json
import logging
import uuid
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler

from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import LOGS_DIR
from backend.models.command import (
    CommandRecord,
    CommandSchema,
    CommandStatus,
    CommandSubmitRequest,
    CommandSubmitResponse,
)
from backend.services.agent_registry import (
    AgentNotFoundError,
    AgentRegistry,
    TaskNotSupportedError,
    build_default_registry,
)

# ---------------------------------------------------------------------------
# Logging setup
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

    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=5_000_000,
        backupCount=5,
        encoding="utf-8",
    )
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
    """Receives commands, logs them, routes them, and tracks their status."""

    def __init__(self, registry: AgentRegistry | None = None) -> None:
        self.registry = registry or build_default_registry()

    # -----------------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------------

    async def receive(
        self,
        db: AsyncSession,
        payload: CommandSubmitRequest,
    ) -> CommandSubmitResponse:
        """
        Full command pipeline.

        IMPORTANT:
        Database transactions are deliberately committed before the agent
        executes. This prevents a long-running LLM request from holding a
        SQLite write transaction open and blocking other commands.
        """

        command_id = str(uuid.uuid4())

        try:
            # ---------------------------------------------------------------
            # 1. Validate
            # ---------------------------------------------------------------
            self.validate(payload)

            # ---------------------------------------------------------------
            # 2. Create command record
            # ---------------------------------------------------------------
            record = await self.log_command(
                db,
                command_id,
                payload,
                CommandStatus.ACCEPTED,
            )

            # Commit immediately.
            #
            # This is critical. Without this commit, SQLite keeps the
            # transaction open while Ollama is processing.
            await db.commit()

            logger.info(
                "COMMAND RECEIVED | id=%s agent=%s task=%s priority=%s",
                command_id,
                payload.agent,
                payload.task,
                payload.priority.value,
            )

            # ---------------------------------------------------------------
            # 3. Mark as PROCESSING and commit
            # ---------------------------------------------------------------
            record = await db.get(CommandRecord, command_id)

            if record is None:
                raise RuntimeError(
                    f"Command record disappeared after creation: {command_id}"
                )

            record.status = CommandStatus.PROCESSING

            await db.commit()

            logger.info(
                "ROUTING | id=%s → agent=%s task=%s",
                command_id,
                payload.agent,
                payload.task,
            )

            # ---------------------------------------------------------------
            # 4. Run the agent
            #
            # NO database transaction is held during this operation.
            # Ollama can take minutes without locking SQLite.
            # ---------------------------------------------------------------
            result = await self.route(
                payload.agent,
                payload.task,
                command_id,
                parameters=payload.parameters,
            )

            # ---------------------------------------------------------------
            # 5. Save completed result
            # ---------------------------------------------------------------
            record = await db.get(CommandRecord, command_id)

            if record is None:
                raise RuntimeError(
                    f"Command record disappeared before completion: {command_id}"
                )

            record.status = CommandStatus.COMPLETED
            record.result = json.dumps(result)

            await db.commit()

            logger.info(
                "COMMAND COMPLETED | id=%s agent=%s task=%s",
                command_id,
                payload.agent,
                payload.task,
            )

            return CommandSubmitResponse(
                status="accepted",
                command_id=command_id,
            )

        except (
            CommandValidationError,
            AgentNotFoundError,
            TaskNotSupportedError,
        ) as exc:
            await self._reject(
                db,
                command_id,
                payload,
                exc,
            )
            raise

        except Exception as exc:
            logger.exception(
                "COMMAND FAILED | id=%s error=%s",
                command_id,
                exc,
            )

            await self._fail(
                db,
                command_id,
                payload,
                exc,
            )

            raise

    async def get_command(
        self,
        db: AsyncSession,
        command_id: str,
    ) -> CommandSchema | None:
        """Retrieve a command by ID."""

        record = await db.get(CommandRecord, command_id)

        if record is None:
            return None

        return CommandSchema.model_validate(record)

    # -----------------------------------------------------------------------
    # Validation
    # -----------------------------------------------------------------------

    def validate(self, payload: CommandSubmitRequest) -> None:
        """Validate agent name and task before routing."""

        agent = payload.agent.strip().lower()
        task = payload.task.strip()

        if not agent:
            raise CommandValidationError(
                "Agent name cannot be empty"
            )

        if not task:
            raise CommandValidationError(
                "Task cannot be empty"
            )

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
            raise TaskNotSupportedError(
                agent,
                task,
                handler.supported_tasks,
            )

    # -----------------------------------------------------------------------
    # Database operations
    # -----------------------------------------------------------------------

    async def log_command(
        self,
        db: AsyncSession,
        command_id: str,
        payload: CommandSubmitRequest,
        status: CommandStatus,
    ) -> CommandRecord:
        """Create and flush a command record."""

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
        """Route a command to the registered agent handler."""

        handler = self.registry.get(agent)

        logger.info(
            "ROUTING | id=%s → agent=%s task=%s",
            command_id,
            agent,
            task,
        )

        return await handler.execute(
            task=task,
            command_id=command_id,
            **(parameters or {}),
        )

    # -----------------------------------------------------------------------
    # Error handling
    # -----------------------------------------------------------------------

    async def _reject(
        self,
        db: AsyncSession,
        command_id: str,
        payload: CommandSubmitRequest,
        exc: Exception,
    ) -> None:
        """Persist a rejected command."""

        await db.rollback()

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

        await db.commit()

    async def _fail(
        self,
        db: AsyncSession,
        command_id: str,
        payload: CommandSubmitRequest,
        exc: Exception,
    ) -> None:
        """Persist a failed command."""

        await db.rollback()

        record = await db.get(
            CommandRecord,
            command_id,
        )

        if record is not None:
            record.status = CommandStatus.FAILED
            record.result = str(exc)
        else:
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

        await db.commit()