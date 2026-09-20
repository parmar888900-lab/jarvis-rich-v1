"""Real read-only YouTube analytics runtime smoke test."""

import asyncio

from backend.database import (
    async_session,
    init_db,
)
from backend.services.agent_handlers.youtube import (
    YoutubeAgentHandler,
)
from backend.services.intelligence.production_selector import (
    ProductionTopicSelector,
)


def candidate():
    return {
        "title": (
            "Why AI generated videos "
            "are becoming more realistic"
        ),
        "source": "runtime-smoke-test",
        "final_score": 82.0,
        "category": "Technology",
        "knowledge": {
            "score": 85.0,
            "category": "Technology",
            "summary": (
                "Synthetic candidate used only "
                "to verify selector integration."
            ),
            "facts": [
                "Fact one.",
                "Fact two.",
                "Fact three.",
            ],
            "sources": [
                {"source": "A"},
                {"source": "B"},
            ],
        },
    }


async def main():
    print("=" * 72)
    print(
        "REAL YOUTUBE ANALYTICS -> "
        "SELECTOR SMOKE TEST"
    )
    print("=" * 72)

    # Ensure the real analytics table exists.
    await init_db()

    handler = YoutubeAgentHandler()

    (
        performance,
        analytics,
    ) = await handler._performance_evidence()

    print()
    print("ANALYTICS STATUS")
    print("-" * 72)

    print(
        "status:",
        analytics.get("status"),
    )

    print(
        "channel_id:",
        analytics.get("channel_id"),
    )

    print(
        "collected_video_count:",
        analytics.get(
            "collected_video_count"
        ),
    )

    print(
        "snapshot_count:",
        analytics.get(
            "snapshot_count"
        ),
    )

    print(
        "unique_video_count:",
        analytics.get(
            "unique_video_count"
        ),
    )

    print(
        "eligible_video_count:",
        analytics.get(
            "eligible_video_count"
        ),
    )

    print(
        "total_views:",
        analytics.get(
            "total_views"
        ),
    )

    print(
        "confidence:",
        analytics.get(
            "confidence"
        ),
    )

    print(
        "strategy_ready:",
        analytics.get(
            "strategy_ready"
        ),
    )

    if performance is None:
        raise AssertionError(
            "Real analytics unexpectedly "
            "failed neutral."
        )

    assert (
        analytics["status"]
        == "success"
    )

    assert (
        analytics["channel_id"]
    )

    print()
    print(
        "PASS: real YouTube analytics "
        "reached runtime evidence service."
    )

    selector = ProductionTopicSelector()

    trend = candidate()

    winner = selector.select(
        [trend],
        performance=performance,
    )

    assert winner is not None

    selection = winner[
        "production_selection"
    ]

    print()
    print("SELECTOR RESULT")
    print("-" * 72)

    print(
        "base_production_score:",
        selection.get(
            "base_production_score"
        ),
    )

    print(
        "historical_adjustment:",
        selection.get(
            "historical_adjustment"
        ),
    )

    print(
        "production_score:",
        selection.get(
            "production_score"
        ),
    )

    historical = selection.get(
        "historical_evidence",
        {},
    )

    print(
        "historical_reason:",
        historical.get(
            "reason"
        ),
    )

    print(
        "historical_confidence:",
        historical.get(
            "confidence"
        ),
    )

    print(
        "historical_match_count:",
        historical.get(
            "match_count"
        ),
    )

    if (
        performance.get(
            "strategy_ready"
        )
        is not True
    ):
        assert (
            selection[
                "historical_adjustment"
            ]
            == 0.0
        )

        assert (
            selection[
                "production_score"
            ]
            == selection[
                "base_production_score"
            ]
        )

        print()
        print(
            "PASS: current real channel "
            "evidence is not strategy-ready, "
            "so historical influence remains "
            "exactly neutral."
        )
    else:
        adjustment = float(
            selection[
                "historical_adjustment"
            ]
        )

        assert (
            -8.0
            <= adjustment
            <= 8.0
        )

        print()
        print(
            "PASS: strategy-ready historical "
            "influence remains inside the "
            "bounded +/-8 score contract."
        )

    print()
    print(
        "PASS: no video generation or "
        "YouTube upload was requested."
    )

    print("=" * 72)
    print(
        "REAL YOUTUBE ANALYTICS -> "
        "SELECTOR SMOKE TEST PASSED"
    )
    print("=" * 72)


asyncio.run(main())
