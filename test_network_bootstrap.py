from argparse import Namespace

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.models.network_channel import NetworkChannel
from scripts.configure_network_channel import register


@pytest.mark.asyncio
async def test_cli_registration_does_not_invent_youtube_authorization(tmp_path, monkeypatch):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'bootstrap.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(NetworkChannel.__table__.create)
    args = Namespace(name="SpaceDecoded", niche="science", editorial="Webb engineering",
                     allow_topic=["Webb"], block_topic=[], max_daily=2,
                     timezone="America/Edmonton", activate=True)
    channel = await register(args, sessions=async_sessionmaker(engine, expire_on_commit=False))
    assert channel.lifecycle_state == "ACTIVE" and channel.max_daily_posts == 2
    assert channel.youtube_channel_id is None and channel.oauth_state is None
    assert __import__("os").environ["JARVIS_PUBLIC_PUBLISH_ENABLED"] == "false"
    await engine.dispose()
