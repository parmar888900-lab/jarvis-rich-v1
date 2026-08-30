"""Production orchestration API routes."""

from uuid import uuid4

from fastapi import APIRouter, HTTPException

from backend.services.orchestration.production_orchestrator import (
    ProductionOrchestrator,
)

router = APIRouter()
orchestrator = ProductionOrchestrator()


@router.post("/production/cycle")
async def run_production_cycle():
    """Run one complete analyze-to-production cycle."""

    cycle_id = str(uuid4())

    try:
        result = await orchestrator.run_cycle(
            cycle_id
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail={
                "error": "production_cycle_failed",
                "detail": "Production cycle failed",
            },
        ) from exc

    return result
