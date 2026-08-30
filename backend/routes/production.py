"""Production orchestration API routes."""

import json

from fastapi import (
    APIRouter,
    HTTPException,
    Request,
)

from backend.database import async_session
from backend.services.orchestration.production_orchestrator import (
    ProductionOrchestrator,
)
from backend.services.orchestration.production_runner import (
    ProductionCycleBusyError,
    ProductionRunner,
)
from backend.services.orchestration.production_runtime import (
    production_lock,
)
from backend.services.production_cycle_service import (
    ProductionCycleService,
)

router = APIRouter()

cycle_service = ProductionCycleService()

orchestrator = ProductionOrchestrator(
    cycle_service=cycle_service,
    session_factory=async_session,
)


@router.get("/production/status")
async def get_production_status(
    request: Request,
):
    """Return current autonomous-production state."""

    scheduler = getattr(
        request.app.state,
        "production_scheduler",
        None,
    )

    async with async_session() as session:
        latest_cycle = (
            await cycle_service.get_latest_cycle(
                session
            )
        )

    latest = None

    if latest_cycle is not None:
        result = None

        if latest_cycle.result:
            try:
                result = json.loads(
                    latest_cycle.result
                )
            except json.JSONDecodeError:
                result = {
                    "raw": latest_cycle.result,
                }

        latest = {
            "cycle_id": latest_cycle.id,
            "status": latest_cycle.status.value,
            "selected_topic": (
                latest_cycle.selected_topic
            ),
            "production_score": (
                latest_cycle.production_score
            ),
            "started_at": (
                latest_cycle.started_at.isoformat()
                if latest_cycle.started_at
                else None
            ),
            "completed_at": (
                latest_cycle.completed_at.isoformat()
                if latest_cycle.completed_at
                else None
            ),
            "result": result,
        }

    return {
        "production": {
            "busy": production_lock.locked(),
        },
        "scheduler": {
            "available": scheduler is not None,
            "enabled": (
                scheduler.enabled
                if scheduler is not None
                else False
            ),
            "running": (
                scheduler.running
                if scheduler is not None
                else False
            ),
            "interval_seconds": (
                scheduler.interval_seconds
                if scheduler is not None
                else None
            ),
        },
        "latest_cycle": latest,
    }


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
