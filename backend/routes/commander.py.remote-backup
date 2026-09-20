"""Commander REST API — POST /command endpoint."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models.command import (
    CommandErrorResponse,
    CommandSchema,
    CommandSubmitRequest,
    CommandSubmitResponse,
)
from backend.services.agent_registry import AgentNotFoundError, TaskNotSupportedError
from backend.services.commander import CommandValidationError, Commander

router = APIRouter()
commander = Commander()


@router.post(
    "/command",
    response_model=CommandSubmitResponse,
    responses={
        400: {"model": CommandErrorResponse, "description": "Validation error"},
        404: {"model": CommandErrorResponse, "description": "Agent not found"},
        422: {"model": CommandErrorResponse, "description": "Task not supported"},
        500: {"model": CommandErrorResponse, "description": "Internal error"},
    },
)
async def submit_command(
    payload: CommandSubmitRequest,
    db: AsyncSession = Depends(get_db),
):
    """Accept a command, validate it, route to the target agent, and return a command ID."""
    try:
        return await commander.receive(db, payload)

    except CommandValidationError as exc:
        raise HTTPException(
            status_code=400,
            detail={"error": "validation_error", "detail": exc.detail},
        ) from exc

    except AgentNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail={"error": "agent_not_found", "detail": str(exc)},
        ) from exc

    except TaskNotSupportedError as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "task_not_supported",
                "detail": str(exc),
            },
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "detail": "Command processing failed"},
        ) from exc


@router.get("/command/{command_id}", response_model=CommandSchema)
async def get_command_status(
    command_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Retrieve the full status and result of a previously submitted command."""
    record = await commander.get_command(db, command_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Command not found")
    return record
