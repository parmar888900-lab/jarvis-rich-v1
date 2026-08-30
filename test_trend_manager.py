from backend.services.providers.registry import (
    build_trend_manager,
)


manager = build_trend_manager()

print("PROVIDERS:")
for provider in manager.providers:
    print(
        f"- {provider.name}"
    )

print()

trends = manager.get_trends(
    limit=10,
)

print("TREND COUNT:", len(trends))

for index, trend in enumerate(
    trends,
    start=1,
):
    print()
    print(
        f"{index}. {trend.get('title')}"
    )
    print(
        "   SOURCE:",
        trend.get("source"),
    )
    print(
        "   SCORE:",
        trend.get("score"),
    )

print()
print(
    "PASS: baseline trend collection completed."
)
