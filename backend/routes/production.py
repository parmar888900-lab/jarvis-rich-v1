"""Production orchestration API routes."""

import asyncio
from uuid import uuid4

from fastapi import APIRouter, HTTPException

from backend.database import async_session
from backend.services.orchestration.production_orchestrator import (
    ProductionOrchestrator,
)
from backend.services.production_cycle_service import (
    ProductionCycleService,
)

router = APIRouter()

orchestrator = ProductionOrchestrator(
    cycle_service=ProductionCycleService(),
    session_factory=async_session,
)

production_lock = asyncio.Lock()


@router.post("/production/cycle")
async def run_production_cycle():
    """Run one complete analyze-to-production cycle."""

    if production_lock.locked():
        raise HTTPException(
            status_code=409,
            detail={
                "error": "production_cycle_busy",
                "detail": (
                    "Another production cycle "
                    "is already running."
                ),
            },
        )

    await production_lock.acquire()

    cycle_id = str(uuid4())

    try:
        result = await orchestrator.run_cycle(
            cycle_id
        )

        return result

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail={
                "error": "production_cycle_failed",
                "detail": "Production cycle failed",
            },
        ) from exc

    finally:
        production_lock.release()
