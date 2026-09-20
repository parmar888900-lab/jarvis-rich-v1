from backend.services.research.evergreen_research_service import (
    EvergreenResearchService,
)


def test_jwst_aliases_outrank_generic_gold_keyword():
    queries = EvergreenResearchService()._research_queries(
        "Why the James Webb Telescope's Gold Mirror Must Unfold in Space"
    )

    assert queries[1:5] == [
        "James Webb Space Telescope mirror unfolding",
        "James Webb Space Telescope",
        "Optical Telescope Element",
        "Segmented mirror",
    ]
    assert "Gold" not in queries[:4]
    assert queries == [
        "Why the James Webb Telescope's Gold Mirror Must Unfold in Space",
        "James Webb Space Telescope mirror unfolding",
        "James Webb Space Telescope",
        "Optical Telescope Element",
        "Segmented mirror",
    ]


def test_exact_premise_remains_first_query():
    topic = "Why train wheels differ from car wheels"
    queries = EvergreenResearchService()._research_queries(topic)

    assert queries[0] == topic
