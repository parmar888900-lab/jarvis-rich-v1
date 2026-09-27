import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.models.network_channel import NetworkChannel
from backend.models.network_control import NetworkControl
from backend.models.network_job import NetworkJob
from backend.models.network_allocation import NetworkAllocation
from backend.models.human_action import HumanAction
from backend.models.youtube_performance_snapshot import YoutubePerformanceSnapshotRecord
from backend.services.network.voice_commands import parse_network_command, route_network_command


def test_narrow_network_voice_grammar():
    assert parse_network_command("how many videos are rendering?")[0] == "rendering_count"
    assert parse_network_command("what failed overnight?")[0] == "recent_failures"
    assert parse_network_command("stop publishing but keep rendering")[0] == "pause_publishing"
    assert parse_network_command("Jarvis, enable publishing") is None
    assert parse_network_command("confirm resume production") == ("resume_production", None, True)


@pytest.mark.asyncio
async def test_voice_uses_persisted_channel_controls_and_confirmation(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path/'voice.db'}")
    async with engine.begin() as conn:
        for model in (NetworkChannel, NetworkControl, NetworkJob, NetworkAllocation,
                      HumanAction, YoutubePerformanceSnapshotRecord):
            await conn.run_sync(model.__table__.create)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with sessions() as db:
        db.add(NetworkChannel(name="BatteryDecoded", niche="engineering",
                              editorial_identity="battery engineering"))
        await db.commit()
    result = await route_network_command("pause BatteryDecoded", sessions, root=tmp_path)
    assert result["status"] == "completed"
    assert "publishing remains off" in result["message"].lower()
    assert (await route_network_command("resume BatteryDecoded", sessions,
                                        root=tmp_path))["status"] == "confirmation_required"
    assert (await route_network_command("confirm resume BatteryDecoded", sessions,
                                        root=tmp_path))["status"] == "completed"
    assert (await route_network_command("how many videos are rendering", sessions,
                                        root=tmp_path))["message"] == "0 videos rendering."
    async with sessions() as db:
        assert (await db.get(NetworkControl, "global")) is None
        assert (await db.get(NetworkChannel, result["result"]["channel_id"])).paused is False
    await engine.dispose()
