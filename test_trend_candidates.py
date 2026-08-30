from collections import Counter

from backend.services.providers.registry import (
    build_trend_manager,
)


manager = build_trend_manager()

trends = manager.collect_candidates(
    per_provider_limit=10,
)

sources = Counter(
    trend.get("source", "Unknown")
    for trend in trends
)

print("TOTAL CANDIDATES:", len(trends))
print()

print("SOURCE COUNTS:")
for source, count in sources.items():
    print(
        f"- {source}: {count}"
    )

print()

for index, trend in enumerate(
    trends,
    start=1,
):
    print(
        f"{index}. "
        f"[{trend.get('source')}] "
        f"{trend.get('title')}"
    )

assert len(trends) > 10
assert sources.get("YouTube", 0) > 0
assert sources.get("Google News RSS", 0) > 0

print()
print(
    "PASS: TrendManager preserves "
    "the multi-provider candidate pool."
)
