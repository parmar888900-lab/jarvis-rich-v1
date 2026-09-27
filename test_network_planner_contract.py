from types import SimpleNamespace

import pytest

from backend.services.intelligence.evergreen_content_selector import EvergreenContentSelector
from backend.services.research.knowledge_pack import KnowledgePack
from backend.services.research.evergreen_research_service import EvergreenResearchService
from scripts.plan_network_day import select_candidate, select_candidates


@pytest.mark.asyncio
async def test_planner_passes_channel_rules_and_researches_selected_evergreen(tmp_path, monkeypatch):
    monkeypatch.setattr(EvergreenContentSelector, "STATE_PATH", tmp_path / "selector.json")
    selector = EvergreenContentSelector()
    channel = SimpleNamespace(id="space", allowed_topics=["Webb"], blocked_topics=["rumor"])
    calls = []

    async def route(**kwargs):
        calls.append(kwargs)
        rules = kwargs["parameters"]
        trend = selector.select(content_id="space", allowed_topics=rules["allowed_topics"],
                                blocked_topics=rules["blocked_topics"])
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
    assert calls[0]["parameters"] == {"allowed_topics": ["Webb"],
                                       "blocked_topics": ["rumor"], "candidate_limit": 4}
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


@pytest.mark.asyncio
async def test_real_commander_routes_channel_rules_to_real_youtube_handler(tmp_path, monkeypatch):
    """Use the production route signature; a **kwargs stub hid the Windows failure."""
    from backend.services.agent_handlers.youtube import YoutubeAgentHandler
    from backend.services.agent_registry import AgentRegistry
    from backend.services.commander import Commander

    monkeypatch.setattr(EvergreenContentSelector, "STATE_PATH", tmp_path / "selector.json")
    handler = YoutubeAgentHandler()

    async def no_analytics():
        return None, {"status": "unavailable"}

    async def no_goal():
        return None, {"status": "unavailable"}

    monkeypatch.setattr(handler, "_performance_evidence", no_analytics)
    monkeypatch.setattr(handler, "_goal_strategy", no_goal)
    registry = AgentRegistry()
    registry.register(handler)
    channel = SimpleNamespace(id="space", allowed_topics=["Webb"], blocked_topics=["rumor"])
    result = await select_candidate(channel, route=Commander(registry=registry).route,
        research=lambda topic: KnowledgePack(topic=topic, score=81,
            sources=[{"url": "https://images.nasa.gov/details/Webb"}],
            facts=["NASA describes Webb's mirror deployment."]))
    assert result is not None and "Webb" in result["topic"]
    assert result["evidence"] == .81
    assert handler.pipeline is None  # Analysis did not instantiate rendering.


@pytest.mark.asyncio
async def test_researched_weak_webb_candidate_yields_to_measured_strong_alternative(
        tmp_path, monkeypatch, capsys):
    from backend.services.agent_handlers.youtube import YoutubeAgentHandler
    from backend.services.agent_registry import AgentRegistry
    from backend.services.commander import Commander

    monkeypatch.setattr(EvergreenContentSelector, "STATE_PATH", tmp_path / "selector.json")
    handler = YoutubeAgentHandler()

    async def no_analytics():
        return None, {"status": "unavailable"}

    async def no_goal():
        return None, {"status": "unavailable"}

    monkeypatch.setattr(handler, "_performance_evidence", no_analytics)
    monkeypatch.setattr(handler, "_goal_strategy", no_goal)
    registry = AgentRegistry()
    registry.register(handler)
    calls = []

    def research(topic):
        calls.append(topic)
        source_title = "James Webb Space Telescope" if len(calls) == 1 else topic

        class SourceProvider:
            def __init__(self, name):
                self.name = name

            def research(self, query):
                if query != topic:
                    return []
                return [{"title": source_title, "source": self.name,
                    "url": f"https://example.org/{self.name}/{len(calls)}",
                    "confidence": .95,
                    "content": "This source describes Webb mirror and sunshield engineering in detail."}]

        service = EvergreenResearchService()
        service.nasa = SourceProvider("NASA Images")
        service.wikipedia = SourceProvider("Wikipedia")
        return service.research(topic)

    channel = SimpleNamespace(id="space", allowed_topics=["Webb"], blocked_topics=[])
    viable = await select_candidates(channel, route=Commander(registry=registry).route,
                                      research=research)
    assert len(calls) >= 2 and calls[0] != calls[1]
    assert viable and viable[0]["topic"] == calls[1]
    assert viable[0]["evidence"] >= .55
    output = capsys.readouterr().out
    assert '"research_confidence":' in output
    assert '"production_score":' in output
    assert '"reason": "measured_score_below_threshold"' in output
    assert '"reason": "eligible_for_originality_reservation"' in output
