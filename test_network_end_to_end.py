"""Safe real-SQLite dry run of the autonomous QA-only network path."""

from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.models.human_action import HumanAction
from backend.models.network_allocation import NetworkAllocation
from backend.models.network_channel import NetworkChannel
from backend.models.network_control import NetworkControl
from backend.models.network_identity import NetworkContentIdentity
from backend.models.network_job import NetworkJob, NetworkJobEvent
from backend.services.network.allocation import DailyAllocator
from backend.services.network.channel_registry import ChannelRegistry
from backend.services.network.production_bridge import ProductionBridge
from backend.services.network.status import network_snapshot
from backend.services.network.topic_source import candidate_from_analysis


class EngineBoundary:
    def __init__(self, path, package):
        self.path, self.package = path, package
        self.calls = []

    async def run_cycle(self, cycle_id, *, selected_trend):
        self.calls.append((cycle_id, selected_trend))
        return {"status": "awaiting_qa", "video_path": str(self.path),
                "selected_trend": selected_trend,
                "production": {"production_package": {"package_dir": str(self.package)}}}


@pytest.mark.asyncio
async def test_channel_to_qa_lineage_and_status_survives_restart(tmp_path, monkeypatch):
    monkeypatch.setenv("JARVIS_PUBLIC_PUBLISH_ENABLED", "false")
    url = f"sqlite+aiosqlite:///{tmp_path / 'network.db'}"
    engine = create_async_engine(url)
    async with engine.begin() as connection:
        for model in (NetworkChannel, NetworkJob, NetworkJobEvent, NetworkContentIdentity,
                      NetworkAllocation, NetworkControl, HumanAction):
            await connection.run_sync(model.__table__.create)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with sessions() as db:
        channel = await ChannelRegistry().register(db, name="SpaceDecoded", niche="science",
                                                   editorial_identity="Webb mechanics",
                                                   allowed_topics=["Webb"], max_daily_posts=2)
        await ChannelRegistry().set_state(db, channel.id, "ACTIVE")
        analysis = {"status": "success", "best_trend": {
            "title": "Webb mirror deployment", "production_selection": {
                "eligible": True, "selected": True, "production_score": 91,
                "research_confidence": 88, "suitability_score": 90}}}
        candidate = candidate_from_analysis(channel, analysis)
        assert candidate is not None
        decision = await DailyAllocator().allocate(
            db, channel_id=channel.id, candidates=[candidate],
            at=datetime.now(timezone.utc))
        assert decision.target == 1
        job_id = decision.selected_job_ids[0]
    await engine.dispose()

    video = tmp_path / "actual-test-boundary.mp4"
    video.write_bytes(b"nonempty local render boundary")
    package = tmp_path / "package"
    package.mkdir()
    (package / "script.txt").write_text("A mirror folded for launch.")
    (package / "metadata.json").write_text('{"metadata":{"evidence_ids":["NASA:Webb"]}}')
    restarted = create_async_engine(url)
    sessions = async_sessionmaker(restarted, expire_on_commit=False)
    renderer = EngineBoundary(video, package)
    await ProductionBridge(sessions, orchestrator=renderer).run(job_id, worker_id="dry-run")
    assert renderer.calls[0][1]["title"] == "Webb mirror deployment"
    async with sessions() as db:
        snapshot = await network_snapshot(db, storage_path=tmp_path)
        assert snapshot["jobs"][0]["state"] == "QA"
        assert snapshot["jobs"][0]["artifacts"]["render"] == str(video)
        assert snapshot["job_counts"] == {"QA": 1}
        assert snapshot["public_publishing_enabled"] is False
        job = await db.get(NetworkJob, job_id)
        assert job.lineage["evidence_ids"] == ["NASA:Webb"]
        assert job.lineage["script_sha256"] and job.lineage["render_sha256"]
        assert job.state != "APPROVED"
    await restarted.dispose()
