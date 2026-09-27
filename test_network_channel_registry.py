"""Real file-backed registry persistence, uniqueness, and pause controls."""

import asyncio

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.models.network_channel import NetworkChannel
from backend.services.network.channel_registry import ChannelRegistry


@pytest.mark.asyncio
async def test_registry_survives_reopen_and_does_not_invent_account_facts(tmp_path):
    url = f"sqlite+aiosqlite:///{tmp_path / 'channels.db'}"
    engine = create_async_engine(url)
    async with engine.begin() as db:
        await db.run_sync(NetworkChannel.__table__.create)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    registry = ChannelRegistry()
    async with sessions() as db:
        channel = await registry.register(
            db, name="SpaceDecoded", niche="engineering", editorial_identity="NASA mechanism explanations",
            timezone="America/Edmonton", topic_universe=["space engineering"],
            profiles={"voice": {"preset": "british_male"}})
        identifier = channel.id
        assert channel.youtube_channel_id is None
        assert channel.oauth_state is None
        assert channel.monetization_state is None
        assert channel.lifecycle_state == "PLANNED"
        with pytest.raises(ValueError, match="already registered"):
            await registry.register(db, name="Copy", niche="engineering",
                                    editorial_identity="NASA mechanism explanations")
        assert (await registry.set_state(db, identifier, "PAUSED")).paused
    await engine.dispose()

    restarted = create_async_engine(url)
    reopened = async_sessionmaker(restarted, expire_on_commit=False)
    async with reopened() as db:
        channels = await registry.list_channels(db)
        assert [c.id for c in channels] == [identifier]
        assert channels[0].voice_profile == {"preset": "british_male"}
        assert channels[0].paused
        assert not (await registry.set_state(db, identifier, "ACTIVE")).paused
    await restarted.dispose()


@pytest.mark.asyncio
async def test_registry_rejects_invalid_quota_conflict_and_timezone(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'channels.db'}")
    async with engine.begin() as db:
        await db.run_sync(NetworkChannel.__table__.create)
    registry = ChannelRegistry()
    async with async_sessionmaker(engine)() as db:
        args = dict(name="A", niche="science", editorial_identity="Distinct voice")
        for kwargs in ({"max_daily_posts": 5}, {"timezone": "Nowhere/Guess"},
                       {"allowed_topics": ["Webb"], "blocked_topics": ["webb"]}):
            with pytest.raises(ValueError):
                await registry.register(db, **args, **kwargs)
        assert await registry.list_channels(db) == []
    await engine.dispose()


@pytest.mark.asyncio
async def test_registry_can_persist_one_hundred_distinct_channels(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'channels.db'}")
    async with engine.begin() as db:
        await db.run_sync(NetworkChannel.__table__.create)
    registry = ChannelRegistry()
    async with async_sessionmaker(engine)() as db:
        for i in range(100):
            await registry.register(db, name=f"Channel{i}", niche="science",
                                    editorial_identity=f"Unique editorial premise {i}")
        assert len(await registry.list_channels(db)) == 100
    await engine.dispose()
