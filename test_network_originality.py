import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.models.network_channel import NetworkChannel
from backend.models.network_identity import NetworkContentIdentity
from backend.models.network_job import NetworkJob, NetworkJobEvent
from backend.services.network.channel_registry import ChannelRegistry
from backend.services.network.job_store import JobStore
from backend.services.network.originality import DuplicateContentError, OriginalityGate


@pytest.mark.asyncio
async def test_persistent_network_wide_near_duplicate_and_lineage_signals(tmp_path):
    url = f"sqlite+aiosqlite:///{tmp_path / 'originality.db'}"
    engine = create_async_engine(url)
    async with engine.begin() as connection:
        for model in (NetworkChannel, NetworkJob, NetworkJobEvent, NetworkContentIdentity):
            await connection.run_sync(model.__table__.create)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with sessions() as db:
        a = await ChannelRegistry().register(db, name="Space", niche="science",
                                             editorial_identity="Webb engineering")
        b = await ChannelRegistry().register(db, name="Tech", niche="technology",
                                             editorial_identity="Hardware mechanics")
        await ChannelRegistry().set_state(db, a.id, "ACTIVE")
        await ChannelRegistry().set_state(db, b.id, "ACTIVE")
        one = await JobStore().enqueue(db, channel_id=a.id, idempotency_key="one")
        two = await JobStore().enqueue(db, channel_id=b.id, idempotency_key="two")
        three = await JobStore().enqueue(db, channel_id=b.id, idempotency_key="three")
    gate = OriginalityGate()
    async with sessions() as db:
        first = await gate.reserve(db, job_id=one.id, topic="How Webb unfolded its giant mirror",
                                   central_claim="The mirror unfolds in space",
                                   hook="A giant telescope had to unfold in space",
                                   source_ids=["nasa:webb:video"],
                                   shot_sequence=["shot1", "shot2", "shot3"])
        assert (await gate.reserve(db, job_id=one.id,
                                   topic="How Webb unfolded its giant mirror")).id == first.id
    await engine.dispose()
    restarted = create_async_engine(url)
    sessions = async_sessionmaker(restarted, expire_on_commit=False)
    async with sessions() as db:
        with pytest.raises(DuplicateContentError) as duplicate:
            await gate.reserve(db, job_id=two.id, topic="How Webb unfolds its giant mirror",
                               central_claim="The mirror unfolds in space")
        assert duplicate.value.conflicting_job_id == one.id
        await db.rollback()
        unique = await gate.reserve(db, job_id=three.id,
                                    topic="Why spacecraft thermal shields reflect sunlight",
                                    source_ids=["nasa:webb:video"],
                                    shot_sequence=["different1", "different2", "different3"])
        assert unique.channel_id == b.id
    await restarted.dispose()
