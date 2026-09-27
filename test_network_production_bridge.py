"""The real SQLite job record follows the existing production-engine boundary."""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.models.network_channel import NetworkChannel
from backend.models.network_job import NetworkJob, NetworkJobEvent
from backend.models.network_identity import NetworkContentIdentity
from backend.services.network.channel_registry import ChannelRegistry
from backend.services.network.job_store import JobStore
from backend.services.network.originality import OriginalityGate
from backend.services.network.production_bridge import ProductionBridge


class FakeEngine:
    def __init__(self, result):
        self.result = result
        self.calls = []

    async def run_cycle(self, cycle_id, **kwargs):
        self.calls.append(cycle_id)
        return self.result


@pytest.mark.asyncio
async def test_render_stops_at_qa_without_upload_or_auto_approval(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'bridge.db'}")
    async with engine.begin() as connection:
        for model in (NetworkChannel, NetworkJob, NetworkJobEvent, NetworkContentIdentity):
            await connection.run_sync(model.__table__.create)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with sessions() as session:
        channel = await ChannelRegistry().register(session, name="SpaceDecoded", niche="science",
                                                   editorial_identity="Webb engineering")
        await ChannelRegistry().set_state(session, channel.id, "ACTIVE")
        job = await JobStore().enqueue(session, channel_id=channel.id,
                                       idempotency_key="webb:one")
        job_id = job.id
    video = tmp_path / "complete.mp4"
    video.write_bytes(b"placeholder for filesystem boundary")
    package = tmp_path / "package"
    package.mkdir()
    (package / "script.txt").write_text("Webb unfolded its mirror.")
    (package / "metadata.json").write_text('{"metadata":{"evidence_ids":["NASA:123"]}}')
    async with sessions() as session:
        await OriginalityGate().reserve(session, job_id=job_id, topic="Webb mirror")
    fake = FakeEngine({"status": "awaiting_qa", "video_path": str(video),
                       "production": {"production_package": {"package_dir": str(package)}}})
    result = await ProductionBridge(sessions, orchestrator=fake).run(job_id, worker_id="worker")
    assert result["status"] == "awaiting_qa"
    assert fake.calls[0].startswith(f"network-{job_id}-attempt-0")
    async with sessions() as session:
        saved = await session.get(NetworkJob, job_id)
        assert saved.state == "QA"
        assert saved.artifacts["render"] == str(video)
        assert saved.lineage["production_cycle"] == fake.calls[0]
        assert saved.lineage["evidence_ids"] == ["NASA:123"]
        assert saved.lineage["render_sha256"]
        identity = await session.scalar(select(NetworkContentIdentity).where(
            NetworkContentIdentity.job_id == job_id))
        assert identity.script == "Webb unfolded its mirror."
        assert saved.worker_id is None
        second = await JobStore().enqueue(session, channel_id=channel.id,
                                          idempotency_key="other", topic="Mars rotor")
        await OriginalityGate().reserve(session, job_id=second.id, topic="Mars rotor")
    await ProductionBridge(sessions, orchestrator=fake).run(second.id, worker_id="worker")
    async with sessions() as session:
        second_saved = await session.get(NetworkJob, second.id)
        assert second_saved.state == "REPAIR"
        assert second_saved.retry_after is not None
    with pytest.raises(ValueError, match="Only queued"):
        await ProductionBridge(sessions, orchestrator=fake).run(job_id, worker_id="worker")
    await engine.dispose()


@pytest.mark.asyncio
async def test_no_action_and_missing_artifact_are_durable(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'bridge.db'}")
    async with engine.begin() as connection:
        for model in (NetworkChannel, NetworkJob, NetworkJobEvent, NetworkContentIdentity):
            await connection.run_sync(model.__table__.create)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with sessions() as session:
        channel = await ChannelRegistry().register(session, name="A", niche="science",
                                                   editorial_identity="science facts")
        await ChannelRegistry().set_state(session, channel.id, "ACTIVE")
        no_topic = await JobStore().enqueue(session, channel_id=channel.id, idempotency_key="a")
        bad = await JobStore().enqueue(session, channel_id=channel.id, idempotency_key="b")
    await ProductionBridge(sessions, orchestrator=FakeEngine({"status": "no_action"})).run(
        no_topic.id, worker_id="w")
    await ProductionBridge(sessions, orchestrator=FakeEngine({
        "status": "awaiting_qa", "video_path": str(tmp_path / "missing.mp4")
    })).run(bad.id, worker_id="w")
    async with sessions() as session:
        assert (await session.get(NetworkJob, no_topic.id)).state == "COMPLETE"
        assert (await session.get(NetworkJob, bad.id)).state == "REPAIR"
    await engine.dispose()
