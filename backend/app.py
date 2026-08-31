"""JARVIS AI - FastAPI application entry point."""

from contextlib import asynccontextmanager
from datetime import timedelta

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import settings
from backend.database import async_session, init_db
from backend.routes import (
    agents,
    analytics,
    commander,
    health,
    production,
    settings as settings_routes,
)
from backend.services.orchestration.production_operation_recovery_runner import (
    ProductionOperationRecoveryRunner,
)
from backend.services.orchestration.production_scheduler import (
    ProductionScheduler,
)
from backend.services.orchestration.production_scheduler_config import (
    autonomous_production_enabled,
    autonomous_production_interval_seconds,
)
from backend.services.production_cycle_service import (
    ProductionCycleService,
)
from backend.services.runtime import (
    RuntimeCapabilityService,
    RuntimeConfig,
    evaluate_production_readiness,
)


PRODUCTION_STALE_AFTER = timedelta(
    hours=6
)

PRODUCTION_OPERATION_STALE_AFTER_SECONDS = (
    PRODUCTION_STALE_AFTER.total_seconds()
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize resources on startup and clean up on shutdown."""

    await init_db()

    production_cycle_service = (
        ProductionCycleService()
    )

    async with async_session() as session:
        await (
            production_cycle_service
            .recover_stale_cycles(
                session,
                stale_after=PRODUCTION_STALE_AFTER,
            )
        )

    operation_recovery_runner = (
        ProductionOperationRecoveryRunner()
    )

    async with async_session() as session:
        await operation_recovery_runner.run(
            session,
            stale_after_seconds=(
                PRODUCTION_OPERATION_STALE_AFTER_SECONDS
            ),
        )

    runtime_config = (
        RuntimeConfig.from_environment()
    )

    capability_service = (
        RuntimeCapabilityService(
            runtime_config
        )
    )

    autonomous_requested = (
        autonomous_production_enabled()
    )

    capability_report = (
        capability_service.inspect_live()
        if autonomous_requested
        else capability_service.inspect()
    )

    readiness = (
        evaluate_production_readiness(
            autonomous_requested=(
                autonomous_requested
            ),
            report=capability_report,
        )
    )

    production_scheduler = ProductionScheduler(
        production.orchestrator,
        interval_seconds=(
            autonomous_production_interval_seconds()
        ),
        enabled=(
            readiness.scheduler_enabled
        ),
        production_allowed=(
            readiness.production_ready
        ),
    )

    production_scheduler.start()

    app.state.production_scheduler = (
        production_scheduler
    )

    app.state.production_capabilities = (
        capability_report
    )

    app.state.production_readiness = (
        readiness
    )

    try:
        yield
    finally:
        await production_scheduler.stop()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Local-first AI assistant powered by open-source models",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(
    health.router,
    prefix="/api",
    tags=["health"],
)
app.include_router(
    commander.router,
    tags=["commander"],
)
app.include_router(
    production.router,
    tags=["production"],
)
app.include_router(
    agents.router,
    prefix="/api/agents",
    tags=["agents"],
)
app.include_router(
    analytics.router,
    prefix="/api/analytics",
    tags=["analytics"],
)
app.include_router(
    settings_routes.router,
    prefix="/api/settings",
    tags=["settings"],
)


@app.get("/")
async def root():
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "status": "running",
        "docs": "/docs",
    }
