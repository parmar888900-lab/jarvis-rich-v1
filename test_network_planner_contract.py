from types import SimpleNamespace

import pytest

from backend.services.intelligence.evergreen_content_selector import EvergreenContentSelector
from backend.services.research.knowledge_pack import KnowledgePack
from scripts.plan_network_day import select_candidate


@pytest.mark.asyncio
async def test_planner_passes_channel_rules_and_researches_selected_evergreen(tmp_path, monkeypatch):
    monkeypatch.setattr(EvergreenContentSelector, "STATE_PATH", tmp_path / "selector.json")
    selector = EvergreenContentSelector()
    channel = SimpleNamespace(id="space", allowed_topics=["Webb"], blocked_topics=["rumor"])
    calls = []

    async def route(**kwargs):
        calls.append(kwargs)
        trend = selector.select(content_id="space", allowed_topics=kwargs["allowed_topics"],
                                blocked_topics=kwargs["blocked_topics"])
        return {"status": "success", "best_trend": trend}

    def research(topic):
        pack = KnowledgePack(topic=topic, score=79,
                             sources=[{"url": "https://images.nasa.gov/details/Webb"}],
                             facts=["NASA describes the mirror deployment."])
        return pack

    candidate = await select_candidate(channel, route=route, research=research)
    assert candidate is not None and "Webb" in candidate["topic"]
    assert candidate["evidence"] == .79
    assert candidate["selected_trend"]["knowledge"]["facts"]
    assert calls[0]["allowed_topics"] == ["Webb"]
    assert calls[0]["blocked_topics"] == ["rumor"]
    assert calls[0]["command_id"] == "space:network-plan"


@pytest.mark.asyncio
async def test_planner_fails_closed_when_research_has_no_sources():
    channel = SimpleNamespace(id="space", allowed_topics=["Webb"], blocked_topics=[])

    async def route(**_):
        return {"status": "success", "best_trend": {"title": "Webb mirror",
            "production_selection": {"eligible": True, "selected": True,
                                     "production_score": 90, "visual_supply": 90}}}

    assert await select_candidate(channel, route=route,
        research=lambda topic: KnowledgePack(topic=topic, score=95)) is None
