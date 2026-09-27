"""Authenticated read-only Network V1 command-center feed."""

from pathlib import Path

import asyncio
import json

from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend.database import async_session
from backend.services.network.status import network_snapshot
from backend.services.network.controls import apply_control
from backend.services.remote_auth import require_remote_token


router = APIRouter(dependencies=[Depends(require_remote_token)])


class ControlRequest(BaseModel):
    action: str
    channel_id: str | None = None
    confirmed: bool = False


@router.get("/api/network/status")
async def get_network_status():
    async with async_session() as db:
        return await network_snapshot(db, storage_path=Path.cwd())


@router.post("/api/network/control")
async def network_control(payload: ControlRequest):
    try:
        async with async_session() as db:
            return await apply_control(db, payload.action, channel_id=payload.channel_id,
                                       confirmed=payload.confirmed)
    except (ValueError, LookupError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None


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
