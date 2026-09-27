import os

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
import pytest

from backend.models.network_allocation import NetworkAllocation
from backend.models.network_channel import NetworkChannel
from backend.models.network_identity import NetworkContentIdentity
from backend.models.network_job import NetworkJob, NetworkJobEvent
from backend.services.network.allocation import DailyAllocator
from backend.services.network.channel_registry import ChannelRegistry
from scripts import commission_network_job


def measured(topic):
    return {"topic": topic, "quality": .72, "evidence": .72, "visual": .72,
            "originality": 1.0, "selected_trend": {"title": topic,
            "production_selection": {"eligible": True, "selected": True,
                "production_score": 72, "visual_supply": 72},
            "knowledge": {"score": 72, "sources": [
                {"url": "https://images.nasa.gov/details/Webb"}],
                "facts": ["NASA describes the mechanism."]}}}


@pytest.mark.asyncio
async def test_script_skips_duplicate_and_queues_next_without_changing_zero_allocation(
        tmp_path, monkeypatch, capsys):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'network.db'}")
    async with engine.begin() as connection:
        for model in (NetworkChannel, NetworkJob, NetworkJobEvent,
                      NetworkContentIdentity, NetworkAllocation):
            await connection.run_sync(model.__table__.create)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with sessions() as db:
        registry = ChannelRegistry()
        prior = await registry.register(db, name="Prior", niche="science",
            editorial_identity="First Webb channel", allowed_topics=["Webb"])
        channel = await registry.register(db, name="Space", niche="science",
            editorial_identity="Second Webb channel", allowed_topics=["Webb"], max_daily_posts=1)
        for row in (prior, channel):
            await registry.set_state(db, row.id, "ACTIVE")
        await DailyAllocator().commission_one(db, channel_id=prior.id,
            candidate=measured("Webb mirror deployment"))
        sealed = await DailyAllocator().allocate(db, channel_id=channel.id, candidates=[])

    async def noop():
        return None

    calls = []

    async def shortlist(_channel):
        calls.append(_channel.id)
        return [measured("Webb mirror deployment"), measured("Webb sunshield deployment")]

    monkeypatch.setattr(commission_network_job, "init_db", noop)
    monkeypatch.setattr(commission_network_job, "async_session", sessions)
    monkeypatch.setattr(commission_network_job, "select_candidates", shortlist)
    monkeypatch.setenv("JARVIS_PUBLIC_PUBLISH_ENABLED", "true")
    await commission_network_job.run(channel.id)
    await commission_network_job.run(channel.id)
    assert calls == [channel.id]
    assert os.environ["JARVIS_PUBLIC_PUBLISH_ENABLED"] == "false"
    output = capsys.readouterr().out
    assert "reason=network_duplicate" in output and "private_qa_job=" in output
    async with sessions() as db:
        jobs = (await db.scalars(select(NetworkJob).where(
            NetworkJob.channel_id == channel.id))).all()
        assert {job.state for job in jobs} == {"FAILED", "QUEUED"}
        assert (await db.get(NetworkAllocation, sealed.id)).target == 0
    await engine.dispose()
