"""Authenticated read-only Network V1 command-center feed."""

from pathlib import Path

import asyncio
import json

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from backend.database import async_session
from backend.services.network.status import network_snapshot
from backend.services.remote_auth import require_remote_token


router = APIRouter(dependencies=[Depends(require_remote_token)])


@router.get("/api/network/status")
async def get_network_status():
    async with async_session() as db:
        return await network_snapshot(db, storage_path=Path.cwd())


@router.get("/api/network/events")
async def network_events(request: Request):
    """Owner-only bounded SSE snapshots; clients reconcile on every reconnect."""
    async def events():
        sequence = 0
        while not await request.is_disconnected():
            try:
                async with async_session() as db:
                    snapshot = await network_snapshot(db, storage_path=Path.cwd())
                sequence += 1
                snapshot["sequence"] = sequence
                yield f"event: snapshot\ndata: {json.dumps(snapshot, default=str)}\n\n"
            except asyncio.CancelledError:
                raise
            except Exception:
                yield "event: unavailable\ndata: {}\n\n"
            await asyncio.sleep(5)

    return StreamingResponse(events(), media_type="text/event-stream", headers={
        "Cache-Control": "no-store", "X-Accel-Buffering": "no",
    })
