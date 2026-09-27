import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.models.human_action import HumanAction
from backend.models.network_channel import NetworkChannel
from backend.models.network_job import NetworkJob, NetworkJobEvent
from backend.services.network.channel_registry import ChannelRegistry
from backend.services.network.human_actions import HumanActionQueue
from backend.services.network.job_store import JobStore


@pytest.mark.asyncio
async def test_human_only_blocker_persists_and_other_jobs_continue(tmp_path):
    url = f"sqlite+aiosqlite:///{tmp_path / 'human.db'}"
    engine = create_async_engine(url)
    async with engine.begin() as connection:
        for model in (NetworkChannel, NetworkJob, NetworkJobEvent, HumanAction):
            await connection.run_sync(model.__table__.create)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    queue = HumanActionQueue()
    async with sessions() as db:
        channel = await ChannelRegistry().register(db, name="A", niche="science",
                                                   editorial_identity="Space mechanics")
        await ChannelRegistry().set_state(db, channel.id, "ACTIVE")
        blocked = await JobStore().enqueue(db, channel_id=channel.id, idempotency_key="block")
        healthy = await JobStore().enqueue(db, channel_id=channel.id, idempotency_key="healthy")
        await JobStore().start_stage(db, blocked.id, "RESEARCHING", "worker")
        action = await queue.open(db, kind="oauth_consent",
                                  what="Channel authorization expired", why="Owner login required",
                                  user_action="Authorize the channel in the official Google flow",
                                  resume="Revalidate authorization and resume the job",
                                  job_id=blocked.id)
        action_id = action.id
        assert (await db.get(NetworkJob, blocked.id)).state == "HUMAN_ACTION_REQUIRED"
        assert (await db.get(NetworkJob, healthy.id)).state == "QUEUED"
    await engine.dispose()
    restarted = create_async_engine(url)
    async with async_sessionmaker(restarted, expire_on_commit=False)() as db:
        pending = await queue.pending(db)
        assert len(pending) == 1 and pending[0].id == action_id
        await queue.resolve(db, action_id)
        assert not await queue.pending(db)
        assert (await db.get(NetworkJob, blocked.id)).state == "HUMAN_ACTION_REQUIRED"
    await restarted.dispose()
