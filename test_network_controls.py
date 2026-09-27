import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.models.network_channel import NetworkChannel
from backend.models.network_control import NetworkControl
from backend.services.network.controls import apply_control


@pytest.mark.asyncio
async def test_durable_pause_resume_and_no_publish_action(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path/'controls.db'}")
    async with engine.begin() as conn:
        await conn.run_sync(NetworkChannel.__table__.create)
        await conn.run_sync(NetworkControl.__table__.create)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with sessions() as db:
        channel = NetworkChannel(name="Science", niche="science",
                                 editorial_identity="Evidence-first engineering")
        db.add(channel)
        await db.commit()
        await db.refresh(channel)
        await apply_control(db, "pause_production")
        await apply_control(db, "pause_channel", channel_id=channel.id)
        with pytest.raises(ValueError, match="confirmation"):
            await apply_control(db, "resume_production")
        with pytest.raises(ValueError, match="Unsupported"):
            await apply_control(db, "enable_publishing", confirmed=True)
    async with sessions() as db:
        assert (await db.get(NetworkControl, "global")).production_enabled is False
        assert (await db.get(NetworkControl, "global")).publishing_enabled is False
        assert (await db.get(NetworkChannel, channel.id)).paused is True
        await apply_control(db, "resume_production", confirmed=True)
        await apply_control(db, "resume_channel", channel_id=channel.id, confirmed=True)
        assert (await db.get(NetworkControl, "global")).production_enabled is True
    await engine.dispose()
