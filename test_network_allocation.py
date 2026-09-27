from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.models.network_allocation import NetworkAllocation
from backend.models.network_channel import NetworkChannel
from backend.models.network_identity import NetworkContentIdentity
from backend.models.network_job import NetworkJob, NetworkJobEvent
from backend.services.network.allocation import DailyAllocator, PreviouslyRejectedCommission
from backend.services.network.channel_registry import ChannelRegistry
from backend.services.network.originality import DuplicateContentError


def candidate(topic, score):
    return {"topic": topic, "quality": score, "evidence": score,
            "visual": score, "originality": score,
            "selected_trend": {"title": topic, "production_selection": {
                "eligible": True, "selected": True}}}


@pytest.mark.asyncio
async def test_allocate_zero_to_four_idempotently_and_block_cross_channel_duplicates(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'allocation.db'}")
    async with engine.begin() as connection:
        for model in (NetworkChannel, NetworkJob, NetworkJobEvent,
                      NetworkContentIdentity, NetworkAllocation):
            await connection.run_sync(model.__table__.create)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with sessions() as db:
        registry = ChannelRegistry()
        strong = await registry.register(db, name="Space", niche="science",
                                         editorial_identity="Space engineering")
        moderate = await registry.register(db, name="Mechanics", niche="engineering",
                                           editorial_identity="Mechanism analysis")
        paused = await registry.register(db, name="Pause", niche="science",
                                         editorial_identity="Paused channel")
        for channel in (strong, moderate):
            await registry.set_state(db, channel.id, "ACTIVE")
        await registry.set_state(db, paused.id, "PAUSED")
        allocator = DailyAllocator()
        now = datetime(2026, 9, 27, 12, tzinfo=timezone.utc)
        topics = [candidate(topic, .91) for topic in (
            "Webb telescope mirror deployment", "Mars helicopter rotor mechanics",
            "Saturn ring particle collisions", "Ocean thermal vent chemistry",
            "Geothermal turbine blade design")]
        a = await allocator.allocate(db, channel_id=strong.id, candidates=topics, at=now)
        assert a.target == 4 and len(a.selected_job_ids) == 4
        same = await allocator.allocate(db, channel_id=strong.id,
                                        candidates=[candidate("Other", .95)], at=now)
        assert same.id == a.id
        b = await allocator.allocate(db, channel_id=moderate.id,
                                     candidates=[candidate("Geothermal turbine blade design", .75),
                                                 candidate("How planetary gears reverse direction", .75),
                                                 candidate("Why gyroscopes resist rotation", .74)], at=now)
        assert b.target == 2
        assert (await db.scalars(select(NetworkJob).where(NetworkJob.state == "FAILED"))).first()
        c = await allocator.allocate(db, channel_id=paused.id, candidates=topics, at=now)
        assert c.target == 0 and c.rationale["active"] is False
    await engine.dispose()


@pytest.mark.asyncio
async def test_allocation_rejects_unmeasured_opportunity(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'allocation.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(NetworkChannel.__table__.create)
        await connection.run_sync(NetworkAllocation.__table__.create)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with sessions() as db:
        channel = await ChannelRegistry().register(db, name="A", niche="science",
                                                   editorial_identity="Example")
        await ChannelRegistry().set_state(db, channel.id, "ACTIVE")
        with pytest.raises(ValueError, match="measured"):
            await DailyAllocator().allocate(db, channel_id=channel.id,
                                            candidates=[{"topic": "A topic", "quality": 1}])
    await engine.dispose()


@pytest.mark.asyncio
async def test_private_commission_preserves_sealed_zero_allocation_and_originality(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'commission.db'}")
    async with engine.begin() as connection:
        for model in (NetworkChannel, NetworkJob, NetworkJobEvent,
                      NetworkContentIdentity, NetworkAllocation):
            await connection.run_sync(model.__table__.create)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with sessions() as db:
        channel = await ChannelRegistry().register(db, name="Space", niche="science",
            editorial_identity="Webb mechanisms", allowed_topics=["Webb"], max_daily_posts=1)
        await ChannelRegistry().set_state(db, channel.id, "ACTIVE")
        sealed = await DailyAllocator().allocate(db, channel_id=channel.id, candidates=[])
        assert sealed.target == 0
        vetted = candidate("How Webb deployed its mirror", .72)
        vetted["selected_trend"]["production_selection"].update(
            {"production_score": 72, "visual_supply": 72})
        vetted["selected_trend"]["knowledge"] = {"score": 72,
            "sources": [{"url": "https://images.nasa.gov/details/test"}], "facts": ["NASA evidence"]}
        job = await DailyAllocator().commission_one(db, channel_id=channel.id,
                                                      candidate=vetted)
        same = await DailyAllocator().commission_one(db, channel_id=channel.id,
                                                       candidate=vetted)
        assert same.id == job.id
        assert job.scheduler_decision["selection_source"] == "audited_private_commissioning"
        assert job.state == "QUEUED"
        assert (await db.get(NetworkAllocation, sealed.id)).target == 0
        assert (await db.scalars(select(NetworkContentIdentity))).first().job_id == job.id
        weak = {**vetted, "topic": "Webb weak", "quality": .54,
                "evidence": .54, "visual": .54,
                "selected_trend": {**vetted["selected_trend"], "title": "Webb weak",
                    "production_selection": {**vetted["selected_trend"]["production_selection"],
                        "production_score": 54, "visual_supply": 54},
                    "knowledge": {**vetted["selected_trend"]["knowledge"], "score": 54}}}
        with pytest.raises(ValueError, match="threshold"):
            await DailyAllocator().commission_one(db, channel_id=channel.id,
                                                  candidate=weak)
        with pytest.raises(ValueError, match="channel-vetted"):
            await DailyAllocator().commission_one(db, channel_id=channel.id,
                                                  candidate=candidate("Mars rover", .9))
        forged = {**vetted, "evidence": 1.0}
        with pytest.raises(ValueError, match="measured"):
            await DailyAllocator().commission_one(db, channel_id=channel.id,
                                                  candidate=forged)
    await engine.dispose()


@pytest.mark.asyncio
async def test_commission_can_try_new_original_topic_after_duplicate(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'commission-duplicate.db'}")
    async with engine.begin() as connection:
        for model in (NetworkChannel, NetworkJob, NetworkJobEvent,
                      NetworkContentIdentity, NetworkAllocation):
            await connection.run_sync(model.__table__.create)
    sessions = async_sessionmaker(engine, expire_on_commit=False)

    def measured(topic):
        item = candidate(topic, .72)
        item["selected_trend"]["production_selection"].update(
            {"production_score": 72, "visual_supply": 72})
        item["selected_trend"]["knowledge"] = {"score": 72,
            "sources": [{"url": "https://images.nasa.gov/details/Webb"}],
            "facts": ["NASA explains the mechanism."]}
        return item

    async with sessions() as db:
        registry = ChannelRegistry()
        first = await registry.register(db, name="First", niche="science",
            editorial_identity="First Webb lens", allowed_topics=["Webb"], max_daily_posts=1)
        second = await registry.register(db, name="Second", niche="science",
            editorial_identity="Second Webb lens", allowed_topics=["Webb"], max_daily_posts=1)
        for channel in (first, second):
            await registry.set_state(db, channel.id, "ACTIVE")
        sealed = await DailyAllocator().allocate(db, channel_id=second.id, candidates=[])
        prior = await DailyAllocator().commission_one(db, channel_id=first.id,
            candidate=measured("Webb mirror deployment"))
        with pytest.raises(DuplicateContentError):
            await DailyAllocator().commission_one(db, channel_id=second.id,
                candidate=measured("Webb mirror deployment"))
        failed = (await db.scalars(select(NetworkJob).where(
            NetworkJob.channel_id == second.id))).first()
        assert failed.state == "FAILED"
        with pytest.raises(PreviouslyRejectedCommission):
            await DailyAllocator().commission_one(db, channel_id=second.id,
                candidate=measured("Webb mirror deployment"))
        next_job = await DailyAllocator().commission_one(db, channel_id=second.id,
            candidate=measured("Webb sunshield deployment"))
        assert next_job.state == "QUEUED" and next_job.id != failed.id
        assert next_job.scheduler_decision["score"] == .72
        assert (await db.get(NetworkAllocation, sealed.id)).target == 0
        assert prior.id != next_job.id
    await engine.dispose()
