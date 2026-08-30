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
from backend.services.production_cycle_service import (
    ProductionCycleService,
)


PRODUCTION_STALE_AFTER = timedelta(
    hours=6
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

    yield


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
