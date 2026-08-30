from collections import Counter

from backend.services.intelligence.suitability import (
    TopicSuitabilityScorer,
)
from backend.services.intelligence.trend_engine import (
    TrendEngine,
)
from backend.services.providers.registry import (
    build_trend_manager,
)


manager = build_trend_manager()
engine = TrendEngine()
suitability = TopicSuitabilityScorer()

raw = manager.collect_candidates(
    per_provider_limit=10,
)

unique = engine.deduplicator.deduplicate(
    raw
)

for trend in unique:
    trend["initial_score"] = (
        engine.scorer.score(trend)
    )

unique.sort(
    key=lambda trend: trend["initial_score"],
    reverse=True,
)

research_count = min(
    max(5 * 2, 5),
    10,
    len(unique),
)

shortlist = engine._select_research_candidates(
    unique,
    research_count,
)

print()
print("=" * 70)
print("PIPELINE COUNTS")
print("RAW:", len(raw))
print("DEDUPLICATED:", len(unique))
print(
    "RESEARCH SHORTLIST:",
    len(shortlist),
)

print()
print("SHORTLIST SOURCE MIX")

for source, count in Counter(
    trend.get("source", "Unknown")
    for trend in shortlist
).items():
    print(
        f"- {source}: {count}"
    )

evaluated = []

for index, trend in enumerate(
    shortlist,
    start=1,
):
    title = trend.get(
        "title",
        "",
    )

    print()
    print(
        f"[{index}/{len(shortlist)}] "
        f"Researching: {title}"
    )

    knowledge = engine.research.research(
        title
    )

    trend["knowledge"] = (
        knowledge.to_dict()
    )

    final_viral = engine.scorer.score(
        trend
    )

    result = suitability.score(
        trend
    )

    evaluated.append(
        {
            "title": title,
            "source": trend.get(
                "source",
                "Unknown",
            ),
            "viral": final_viral,
            "research": knowledge.score,
            "suitability": result["score"],
            "researchability": (
                result["researchability"]
            ),
            "explainability": (
                result["explainability"]
            ),
            "curiosity": (
                result["curiosity"]
            ),
            "transformation": (
                result["transformation"]
            ),
            "context_penalty": (
                result[
                    "low_context_penalty"
                ]
            ),
            "sensitivity_penalty": (
                result[
                    "sensitivity_penalty"
                ]
            ),
            "research_penalty": (
                result[
                    "research_confidence_penalty"
                ]
            ),
        }
    )


ranked = sorted(
    evaluated,
    key=lambda item: (
        item["suitability"],
        item["viral"],
    ),
    reverse=True,
)


print()
print("=" * 70)
print("RANKED BY SUITABILITY")

for index, item in enumerate(
    ranked,
    start=1,
):
    print()
    print(
        f"{index}. {item['title']}"
    )
    print(
        f"   SOURCE: "
        f"{item['source']}"
    )
    print(
        f"   VIRAL: "
        f"{item['viral']}"
    )
    print(
        f"   RESEARCH: "
        f"{item['research']}"
    )
    print(
        f"   SUITABILITY: "
        f"{item['suitability']}"
    )
    print(
        "   COMPONENTS: "
        f"R={item['researchability']} "
        f"E={item['explainability']} "
        f"C={item['curiosity']} "
        f"T={item['transformation']}"
    )
    print(
        "   PENALTIES: "
        f"context="
        f"{item['context_penalty']} "
        f"sensitive="
        f"{item['sensitivity_penalty']} "
        f"research="
        f"{item['research_penalty']}"
    )


print()
print("=" * 70)
print("TOP 5")

for index, item in enumerate(
    ranked[:5],
    start=1,
):
    print(
        f"{index}. "
        f"[{item['suitability']}] "
        f"{item['title']}"
    )

print()
print(
    "PASS: full live suitability "
    "regression completed."
)
