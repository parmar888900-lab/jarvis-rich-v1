from types import SimpleNamespace

from backend.services.network.topic_source import candidate_from_analysis


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
