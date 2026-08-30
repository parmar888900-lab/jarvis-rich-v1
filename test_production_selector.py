from backend.services.intelligence.production_selector import (
    ProductionTopicSelector,
)


selector = ProductionTopicSelector()


def make_trend(
    title,
    viral,
    research,
    category="News",
    facts=None,
    sources=None,
    summary="Useful researched explanation.",
):
    return {
        "title": title,
        "source": "Test",
        "final_score": viral,
        "category": category,
        "knowledge": {
            "score": research,
            "summary": summary,
            "facts": facts or [
                "Relevant fact one.",
                "Relevant fact two.",
                "Relevant fact three.",
            ],
            "sources": sources or [
                {"source": "Source A"},
                {"source": "Source B"},
                {"source": "Source C"},
            ],
        },
    }


candidates = [
    make_trend(
        "Why scientists discovered a major new technology",
        viral=78,
        research=90,
    ),
    make_trend(
        "THIS IS NOT A GAME",
        viral=98,
        research=10,
        facts=[],
        sources=[],
        summary="",
    ),
    make_trend(
        "Official Music Video New Song",
        viral=95,
        research=80,
    ),
    make_trend(
        "How a new discovery could change technology",
        viral=85,
        research=82,
    ),
]


ranked = selector.rank(candidates)

print("=" * 70)
print("PRODUCTION SELECTOR RANKING")

for index, trend in enumerate(
    ranked,
    start=1,
):
    decision = trend["production_selection"]

    print()
    print(
        f"{index}. {trend['title']}"
    )
    print(
        "   VIRAL:",
        decision["viral_score"],
    )
    print(
        "   RESEARCH:",
        decision["research_confidence"],
    )
    print(
        "   SUITABILITY:",
        decision["suitability_score"],
    )
    print(
        "   PRODUCTION:",
        decision["production_score"],
    )
    print(
        "   ELIGIBLE:",
        decision["eligible"],
    )
    print(
        "   REJECTIONS:",
        decision["rejection_reasons"],
    )


winner = selector.select(candidates)

assert winner is not None

decision = winner["production_selection"]

assert decision["eligible"] is True
assert decision["selected"] is True

assert (
    winner["title"]
    != "THIS IS NOT A GAME"
)

assert selector.select([]) is None


poor_research = next(
    trend
    for trend in candidates
    if trend["title"] == "THIS IS NOT A GAME"
)

assert (
    poor_research["production_selection"][
        "eligible"
    ]
    is False
)

assert (
    "research_confidence_below_threshold"
    in poor_research[
        "production_selection"
    ]["rejection_reasons"]
)


music_video = next(
    trend
    for trend in candidates
    if trend["title"]
    == "Official Music Video New Song"
)

assert (
    music_video["production_selection"][
        "eligible"
    ]
    is False
)


print()
print("=" * 70)
print(
    "WINNER:",
    winner["title"],
)
print(
    "PRODUCTION SCORE:",
    decision["production_score"],
)
print()
print(
    "PASS: production selector rejects "
    "weak candidates and selects a "
    "production-ready topic."
)
