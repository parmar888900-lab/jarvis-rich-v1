from types import SimpleNamespace

from backend.services.network.topic_source import candidate_from_analysis
from backend.services.intelligence.evergreen_content_selector import EvergreenContentSelector


def test_channel_editorial_gate_and_measured_scores():
    channel = SimpleNamespace(allowed_topics=["Webb"], blocked_topics=["rumor"])
    analysis = {"status": "success", "best_trend": {
        "title": "How Webb deployed its mirror", "production_selection": {
            "eligible": True, "selected": True, "production_score": 86,
            "research_confidence": 89, "suitability_score": 79}}}
    candidate = candidate_from_analysis(channel, analysis)
    assert candidate["topic"] == "How Webb deployed its mirror"
    assert candidate["quality"] == .86 and candidate["visual"] == .79
    channel.allowed_topics = ["movie"]
    assert candidate_from_analysis(channel, analysis) is None
    channel.allowed_topics = ["Webb"]
    analysis["best_trend"]["production_selection"].pop("research_confidence")
    assert candidate_from_analysis(channel, analysis) is None


def test_channel_scoped_evergreen_requires_researched_sources(tmp_path, monkeypatch):
    monkeypatch.setattr(EvergreenContentSelector, "STATE_PATH", tmp_path / "state.json")
    selector = EvergreenContentSelector()
    trend = selector.select(content_id="network", allowed_topics=["Webb"],
                            blocked_topics=["rumor"])
    assert "Webb" in trend["title"]
    assert trend["production_selection"]["selected"] is True
    channel = SimpleNamespace(allowed_topics=["Webb"], blocked_topics=["rumor"])
    analysis = {"status": "success", "best_trend": trend}
    assert candidate_from_analysis(channel, analysis) is None
    trend["knowledge"] = {"score": 78, "sources": [{"url": "https://images.nasa.gov/details/test"}],
                          "facts": ["NASA describes mirror deployment."]}
    candidate = candidate_from_analysis(channel, analysis)
    assert candidate["evidence"] == .78
    assert candidate["visual"] == trend["production_selection"]["visual_supply"] / 100
    assert candidate["quality"] == trend["production_selection"]["production_score"] / 100
    channel.allowed_topics = ["Mars"]
    assert candidate_from_analysis(channel, analysis) is None
    channel.allowed_topics = ["Webb"]
    channel.blocked_topics = ["mirror"]
    assert candidate_from_analysis(channel, analysis) is None
    channel.blocked_topics = []
    trend["production_selection"]["selected"] = False
    assert candidate_from_analysis(channel, analysis) is None
    trend["production_selection"]["selected"] = True
    trend["production_selection"]["eligible"] = False
    assert candidate_from_analysis(channel, analysis) is None


def test_evergreen_rejects_unmeasured_or_malformed_evidence():
    channel = SimpleNamespace(allowed_topics=["Webb"], blocked_topics=[])
    trend = {"title": "Webb mirror", "production_selection": {
        "eligible": True, "selected": True, "production_score": 90, "visual_supply": 80}}
    analysis = {"status": "success", "best_trend": trend}
    for knowledge in (None, {}, {"score": 90}, {"score": "unknown", "sources": [{}]},
                      {"score": 90, "sources": []},
                      {"score": 90, "sources": [{}], "facts": ["unsupported"]}):
        trend["knowledge"] = knowledge
        assert candidate_from_analysis(channel, analysis) is None
