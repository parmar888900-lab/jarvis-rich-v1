"""Real SQLite persistence and recovery of Network V1 job transitions."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.models.network_channel import NetworkChannel
from backend.models.network_job import NetworkJob, NetworkJobEvent
from backend.services.network.channel_registry import ChannelRegistry
from backend.services.network.job_store import JobStore


@pytest.mark.asyncio
async def test_idempotency_transition_lineage_and_restart(tmp_path):
    url = f"sqlite+aiosqlite:///{tmp_path / 'jobs.db'}"
    engine = create_async_engine(url)
    async with engine.begin() as db:
        await db.run_sync(NetworkChannel.__table__.create)
        await db.run_sync(NetworkJob.__table__.create)
        await db.run_sync(NetworkJobEvent.__table__.create)
    registry, jobs = ChannelRegistry(), JobStore()
    async with async_sessionmaker(engine, expire_on_commit=False)() as db:
        channel = await registry.register(db, name="SpaceDecoded", niche="science",
                                          editorial_identity="Webb deployment engineering")
        with pytest.raises(ValueError, match="not active"):
            await jobs.enqueue(db, channel_id=channel.id, idempotency_key="day1:topic1")
        await registry.set_state(db, channel.id, "ACTIVE")
        first = await jobs.enqueue(db, channel_id=channel.id, idempotency_key="day1:topic1",
                                   topic="Webb unfolds", scheduler_decision={"score": 0.9})
        again = await jobs.enqueue(db, channel_id=channel.id, idempotency_key="day1:topic1",
                                   topic="Webb unfolds")
        assert first.id == again.id
        with pytest.raises(ValueError, match="different production"):
            await jobs.enqueue(db, channel_id=channel.id, idempotency_key="day1:topic1",
                               topic="Unrelated subject")
        with pytest.raises(ValueError, match="Illegal"):
            await jobs.transition(db, first.id, "APPROVED")
        running = await jobs.start_stage(db, first.id, "RESEARCHING", "worker-1", lease_seconds=30)
        running.lease_until = datetime.now(timezone.utc) - timedelta(seconds=2)
        await db.commit()
        first_id = first.id
    await engine.dispose()

    restarted = create_async_engine(url)
    async with async_sessionmaker(restarted, expire_on_commit=False)() as db:
        assert await jobs.recover_stale(db) == [first_id]
        job = await db.get(NetworkJob, first_id)
        assert job.state == "REPAIR" and job.attempt == 1 and job.worker_id is None
        assert await jobs.recover_stale(db) == []
        await jobs.transition(db, first_id, "RESEARCHING", lineage={"topic": "Webb unfolds"})
        await jobs.transition(db, first_id, "EVIDENCE_READY")
        await jobs.transition(db, first_id, "SCRIPTING")
        await jobs.transition(db, first_id, "SCRIPTED")
        await jobs.transition(db, first_id, "VISUAL_PLANNING")
        await jobs.transition(db, first_id, "MEDIA_RESOLVING")
        await jobs.transition(db, first_id, "MEDIA_READY")
        await jobs.transition(db, first_id, "NARRATING")
        await jobs.transition(db, first_id, "EDITING")
        await jobs.transition(db, first_id, "RENDERING")
        await jobs.transition(db, first_id, "QA")
        with pytest.raises(ValueError, match="QA artifact"):
            await jobs.transition(db, first_id, "APPROVED")
        approved = await jobs.transition(db, first_id, "APPROVED", artifact=("mp4", "/tmp/short.mp4"))
        assert approved.lineage["topic"] == "Webb unfolds"
        assert approved.artifacts["mp4"] == "/tmp/short.mp4"
        await jobs.transition(db, first_id, "COMPLETE")
        events = (await db.scalars(select(NetworkJobEvent).where(NetworkJobEvent.job_id == first_id))).all()
        assert events[0].to_state == "QUEUED" and events[-1].to_state == "COMPLETE"
        assert (await db.get(NetworkJob, first_id)).scheduler_decision == {"score": 0.9}
    await restarted.dispose()


@pytest.mark.asyncio
async def test_exhausted_stale_job_dead_ends_without_affecting_other_jobs(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'jobs.db'}")
    async with engine.begin() as db:
        await db.run_sync(NetworkChannel.__table__.create)
        await db.run_sync(NetworkJob.__table__.create)
        await db.run_sync(NetworkJobEvent.__table__.create)
    jobs = JobStore()
    async with async_sessionmaker(engine, expire_on_commit=False)() as db:
        channel = await ChannelRegistry().register(db, name="A", niche="science",
                                                   editorial_identity="Engineering test")
        await ChannelRegistry().set_state(db, channel.id, "ACTIVE")
        stale = await jobs.enqueue(db, channel_id=channel.id, idempotency_key="one")
        healthy = await jobs.enqueue(db, channel_id=channel.id, idempotency_key="two")
        stale = await jobs.start_stage(db, stale.id, "RESEARCHING", "old", lease_seconds=30)
        stale.attempt = 2
        stale.lease_until = datetime.now(timezone.utc) - timedelta(seconds=1)
        await db.commit()
        assert await jobs.recover_stale(db) == [stale.id]
        assert (await db.get(NetworkJob, stale.id)).state == "FAILED"
        assert (await db.get(NetworkJob, healthy.id)).state == "QUEUED"
    await engine.dispose()
