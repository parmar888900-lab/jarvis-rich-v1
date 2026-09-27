from types import SimpleNamespace

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.models.network_allocation import NetworkAllocation
from backend.models.network_channel import NetworkChannel
from backend.models.network_control import NetworkControl
from backend.models.network_identity import NetworkContentIdentity
from backend.models.network_job import NetworkJob, NetworkJobEvent
from backend.services.network.channel_registry import ChannelRegistry
from backend.services.network.job_store import JobStore
from backend.services.network.supervisor import NetworkSupervisor


@pytest.mark.asyncio
async def test_supervisor_plans_then_runs_persisted_queue_with_kill_and_disk_gates(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'supervisor.db'}")
    async with engine.begin() as connection:
        for model in (NetworkChannel, NetworkJob, NetworkJobEvent,
                      NetworkContentIdentity, NetworkAllocation, NetworkControl):
            await connection.run_sync(model.__table__.create)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    calls = []

    def bounded(command, **kwargs):
        calls.append((command, kwargs))
        assert kwargs["timeout_seconds"] <= 7200
        return SimpleNamespace(returncode=0)

    worker = NetworkSupervisor(sessions, runner=bounded, root=tmp_path)
    async with sessions() as db:
        channel = await ChannelRegistry().register(db, name="Space", niche="science",
                                                   editorial_identity="JWST mechanisms",
                                                   allowed_topics=["Webb"])
        await ChannelRegistry().set_state(db, channel.id, "ACTIVE")
    assert (await worker.tick())["kind"] == "plan"
    assert calls[0][1]["timeout_seconds"] == 1200
    async with sessions() as db:
        control = await db.get(NetworkControl, "global")
        assert control.publishing_enabled is False
        control.accept_new_jobs = False
        await db.commit()
        job = await JobStore().enqueue(db, channel_id=channel.id,
                                       idempotency_key="queued", topic="Webb mirror")
    assert (await worker.tick())["kind"] == "job"
    assert "run_network_job.py" in calls[-1][0][1]
    async with sessions() as db:
        control = await db.get(NetworkControl, "global")
        control.emergency_stop = True
        await db.commit()
    assert (await worker.tick())["status"] == "paused"
    assert len(calls) == 2
    async with sessions() as db:
        control = await db.get(NetworkControl, "global")
        control.emergency_stop = False
        control.min_free_bytes = 10**15
        await db.commit()
    assert (await worker.tick())["status"] == "disk_protection"
    await engine.dispose()


@pytest.mark.asyncio
async def test_failed_planner_enters_persistent_backoff(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'backoff.db'}")
    async with engine.begin() as connection:
        for model in (NetworkChannel, NetworkJob, NetworkJobEvent,
                      NetworkContentIdentity, NetworkAllocation, NetworkControl):
            await connection.run_sync(model.__table__.create)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with sessions() as db:
        channel = await ChannelRegistry().register(db, name="A", niche="science",
                                                   editorial_identity="NASA science",
                                                   allowed_topics=["Webb"])
        await ChannelRegistry().set_state(db, channel.id, "ACTIVE")
    attempts = []

    def failing(command, **kwargs):
        attempts.append(command)
        return SimpleNamespace(returncode=1)

    first = NetworkSupervisor(sessions, runner=failing, root=tmp_path)
    assert (await first.tick())["status"] == "child_failed"
    await engine.dispose()
    reopened = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'backoff.db'}")
    second = NetworkSupervisor(async_sessionmaker(reopened, expire_on_commit=False),
                               runner=failing, root=tmp_path)
    assert (await second.tick())["status"] == "idle"
    assert len(attempts) == 1
    await reopened.dispose()
