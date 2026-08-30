"""Production orchestration API routes."""

from fastapi import APIRouter, HTTPException

from backend.database import async_session
from backend.services.orchestration.production_orchestrator import (
    ProductionOrchestrator,
)
from backend.services.orchestration.production_runner import (
    ProductionCycleBusyError,
    ProductionRunner,
)
from backend.services.production_cycle_service import (
    ProductionCycleService,
)

router = APIRouter()

orchestrator = ProductionOrchestrator(
    cycle_service=ProductionCycleService(),
    session_factory=async_session,
)


@router.post("/production/cycle")
async def run_production_cycle():
    """Run one complete analyze-to-production cycle."""

    runner = ProductionRunner(
        orchestrator
    )

    try:
        return await runner.run_cycle()

    except ProductionCycleBusyError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "production_cycle_busy",
                "detail": str(exc),
            },
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail={
                "error": "production_cycle_failed",
                "detail": "Production cycle failed",
            },
        ) from exc
