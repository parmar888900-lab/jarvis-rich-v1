"""Authenticated read-only Network V1 command-center feed."""

from pathlib import Path

from fastapi import APIRouter, Depends

from backend.database import async_session
from backend.services.network.status import network_snapshot
from backend.services.remote_auth import require_remote_token


router = APIRouter(dependencies=[Depends(require_remote_token)])


@router.get("/api/network/status")
async def get_network_status():
    async with async_session() as db:
        return await network_snapshot(db, storage_path=Path.cwd())
