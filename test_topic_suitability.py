from backend.services.intelligence.suitability import (
    TopicSuitabilityScorer,
)


scorer = TopicSuitabilityScorer()

research = {
    "summary": (
        "Researchers identified new evidence and "
        "explained why the finding matters."
    ),
    "facts": [
        "Fact 1",
        "Fact 2",
        "Fact 3",
        "Fact 4",
    ],
    "sources": [
        {"source": "A"},
        {"source": "B"},
        {"source": "C"},
    ],
    "category": "News",
}


cases = {
    "explainable_news": {
        "title": (
            "Why scientists discovered a new warning "
            "sign in glacier research"
        ),
        "source": "Google News RSS",
        "knowledge": research,
    },
    "music_video": {
        "title": (
            "New Song Official Music Video "
            "Artist Name"
        ),
        "source": "YouTube",
        "knowledge": research,
    },
    "gameplay": {
        "title": (
            "LIVE GTA 5 GAMEPLAY "
            "RAAJOO GAMING"
        ),
        "source": "YouTube",
        "knowledge": research,
    },
}


results = {}

for name, trend in cases.items():
    result = scorer.score(trend)
    results[name] = result

    print()
    print(name.upper())
    print("TOTAL:", result["score"])
    print(
        "RESEARCHABILITY:",
        result["researchability"],
    )
    print(
        "EXPLAINABILITY:",
        result["explainability"],
    )
    print(
        "CURIOSITY:",
        result["curiosity"],
    )
    print(
        "TRANSFORMATION:",
        result["transformation"],
    )
    print(
        "LOW CONTEXT PENALTY:",
        result["low_context_penalty"],
    )
    print(
        "SENSITIVITY PENALTY:",
        result["sensitivity_penalty"],
    )


assert (
    results["explainable_news"]["score"]
    > results["music_video"]["score"]
)

assert (
    results["explainable_news"]["score"]
    > results["gameplay"]["score"]
)

assert (
    results["music_video"]["low_context_penalty"]
    > 0
)

assert (
    results["gameplay"]["low_context_penalty"]
    > 0
)

print()
print(
    "PASS: suitability scoring separates "
    "transformable topics from source-dependent media."
)
