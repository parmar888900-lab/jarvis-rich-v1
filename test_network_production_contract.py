"""Exercise the real Commander → YouTube handler → orchestrator contract.

Only the expensive Rich V1 pipeline is replaced; no upload route is allowed.
"""
import pytest

from backend.services.agent_registry import AgentRegistry
from backend.services.agent_handlers.youtube import YoutubeAgentHandler
from backend.services.commander import Commander
from backend.services.orchestration.production_orchestrator import ProductionOrchestrator


class Generated:
    def to_dict(self):
        return {"title": "A documented Webb Short", "hashtags": []}


class PipelineBoundary:
    def __init__(self, video_path):
        self.path = video_path
        self.trends = []

    async def run(self, trend):
        self.trends.append(trend)
        return {"generated": Generated(), "production_package": {"package_dir": "package"},
                "video": {"video_path": str(self.path)}}


@pytest.mark.asyncio
async def test_selected_network_trend_routes_through_real_interfaces_without_upload(tmp_path):
    handler = YoutubeAgentHandler()
    pipeline = PipelineBoundary(tmp_path / "render.mp4")
    handler.pipeline = pipeline
    registry = AgentRegistry()
    registry.register(handler)
    trend = {"title": "How James Webb Space Telescope aligned its mirror segments",
             "production_selection": {"eligible": True, "selected": True,
                                      "production_score": 79.0},
             "knowledge": {"score": 75, "facts": ["Documented fact"],
                           "sources": [{"url": "https://science.nasa.gov/"}]}}
    result = await ProductionOrchestrator(
        commander=Commander(registry=registry), private_upload_enabled=False).run_cycle(
            "network-checked-attempt-0", selected_trend=trend)
    assert result["status"] == "awaiting_qa"
    assert result["video_path"] == str(pipeline.path)
    assert result["production"]["production_package"]["package_dir"] == "package"
    assert pipeline.trends == [trend]
    assert result["release"] == {"status": "disabled"}
