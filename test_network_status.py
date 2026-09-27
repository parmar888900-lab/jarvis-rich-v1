import pytest
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.models.human_action import HumanAction
from backend.models.network_allocation import NetworkAllocation
from backend.models.network_channel import NetworkChannel
from backend.models.network_control import NetworkControl
from backend.models.network_job import NetworkJob, NetworkJobEvent
from backend.models.youtube_performance_snapshot import YoutubePerformanceSnapshotRecord
from backend.services.network.channel_registry import ChannelRegistry
from backend.services.network.human_actions import HumanActionQueue
from backend.services.network.job_store import JobStore
from backend.services.network.status import network_snapshot


@pytest.mark.asyncio
async def test_status_only_reports_persisted_network_facts(tmp_path, monkeypatch):
    monkeypatch.setenv("JARVIS_PUBLIC_PUBLISH_ENABLED", "false")
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'status.db'}")
    async with engine.begin() as connection:
        for model in (NetworkChannel, NetworkJob, NetworkJobEvent,
                      NetworkAllocation, NetworkControl, HumanAction,
                      YoutubePerformanceSnapshotRecord):
            await connection.run_sync(model.__table__.create)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with sessions() as db:
        channel = await ChannelRegistry().register(db, name="Science", niche="engineering",
                                                   editorial_identity="Mechanics")
        await ChannelRegistry().set_state(db, channel.id, "ACTIVE")
        job = await JobStore().enqueue(db, channel_id=channel.id,
                                       idempotency_key="status", topic="Webb mirror")
        await HumanActionQueue().open(db, kind="oauth", what="Login expired",
                                      why="Owner consent needed", user_action="Sign in",
                                      resume="Revalidate OAuth", job_id=job.id)
        db.add(YoutubePerformanceSnapshotRecord(
            video_id="yt-video", channel_id="yt-channel", title="Observed Short",
            privacy_status="private", captured_at=datetime.now(timezone.utc),
            views=12, likes=3, comments=1))
        await db.commit()
        snapshot = await network_snapshot(db, storage_path=tmp_path)
        assert snapshot["channels"][0]["name"] == "Science"
        assert snapshot["jobs"][0]["state"] == "QUEUED"
        assert snapshot["job_counts"] == {"QUEUED": 1}
        assert snapshot["human_actions"][0]["required_user_action"] == "Sign in"
        assert snapshot["public_publishing_enabled"] is False
        assert snapshot["system"]["disk_free_bytes"] > 0
        assert snapshot["system"]["cpu_percent"] is None
        assert snapshot["analytics"][0]["views"] == 12
    await engine.dispose()


def test_network_status_requires_owner_token(monkeypatch):
    pytest.importorskip("fastapi")
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from backend.routes.network import router
    monkeypatch.setenv("JARVIS_REMOTE_TOKEN", "owner-test-token")
    app = FastAPI()
    app.include_router(router)
    with TestClient(app) as client:
        assert client.get("/api/network/status").status_code == 401
        assert client.get("/api/network/status", headers={
            "Authorization": "Bearer wrong"}).status_code == 401
