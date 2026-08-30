from collections import Counter

from backend.services.intelligence.production_selector import (
    ProductionTopicSelector,
)
from backend.services.intelligence.trend_engine import (
    TrendEngine,
)
from backend.services.providers.registry import (
    build_trend_manager,
)


manager = build_trend_manager()
engine = TrendEngine()
selector = ProductionTopicSelector()


print("=" * 72)
print("COLLECTING LIVE TRENDS")

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
print("RAW:", len(raw))
print("DEDUPLICATED:", len(unique))
print("RESEARCH SHORTLIST:", len(shortlist))

print()
print("SOURCE MIX:")

for source, count in Counter(
    trend.get("source", "Unknown")
    for trend in shortlist
).items():
    print(f"- {source}: {count}")


for index, trend in enumerate(
    shortlist,
    start=1,
):
    title = trend.get("title", "")

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

    trend["final_score"] = (
        engine.scorer.score(trend)
    )


ranked = selector.rank(shortlist)


print()
print("=" * 72)
print("PRODUCTION RANKING")

for index, trend in enumerate(
    ranked,
    start=1,
):
    decision = trend[
        "production_selection"
    ]

    print()
    print(
        f"{index}. "
        f"{trend.get('title', '')}"
    )
    print(
        "   SOURCE:",
        trend.get("source", "Unknown"),
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


winner = selector.select(shortlist)


print()
print("=" * 72)

if winner is None:
    print(
        "NO PRODUCTION-READY TOPIC FOUND"
    )
else:
    decision = winner[
        "production_selection"
    ]

    print("SELECTED TOPIC:")
    print(winner.get("title", ""))

    print()
    print(
        "SOURCE:",
        winner.get("source", "Unknown"),
    )
    print(
        "VIRAL:",
        decision["viral_score"],
    )
    print(
        "RESEARCH:",
        decision["research_confidence"],
    )
    print(
        "SUITABILITY:",
        decision["suitability_score"],
    )
    print(
        "PRODUCTION:",
        decision["production_score"],
    )
    print(
        "REASON:",
        decision["reason"],
    )

print()
print(
    "PASS: live production-selection "
    "pipeline completed."
)
