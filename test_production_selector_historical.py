"""Historical intelligence integration tests for production selection."""

from copy import deepcopy

from backend.services.intelligence.production_selector import (
    ProductionTopicSelector,
)


def make_trend(
    title,
    *,
    viral=80,
    research=85,
    category="Stories",
):
    return {
        "title": title,
        "source": "Test",
        "final_score": viral,
        "category": category,
        "knowledge": {
            "score": research,
            "category": category,
            "summary": (
                "Useful researched explanation."
            ),
            "facts": [
                "Relevant fact one.",
                "Relevant fact two.",
                "Relevant fact three.",
            ],
            "sources": [
                {"source": "Source A"},
                {"source": "Source B"},
            ],
        },
    }


def performance(
    *,
    ready,
    confidence,
    score,
    title=(
        "Customer returned shoes "
        "after wearing them for years"
    ),
):
    return {
        "strategy_ready": ready,
        "confidence": confidence,
        "videos": [
            {
                "video_id": "historical-1",
                "title": title,
                "performance_score": score,
            }
        ],
    }


def main():
    print("=" * 72)
    print(
        "PRODUCTION SELECTOR HISTORICAL "
        "INTEGRATION TEST"
    )
    print("=" * 72)

    selector = ProductionTopicSelector()

    candidate = make_trend(
        "Customer returned shoes after "
        "wearing them for two years"
    )

    # -------------------------------------------------
    # No evidence preserves the old score exactly.
    # -------------------------------------------------

    no_history = deepcopy(
        candidate
    )

    selector.rank(
        [no_history]
    )

    decision = no_history[
        "production_selection"
    ]

    assert (
        decision["historical_adjustment"]
        == 0.0
    )

    assert (
        decision["production_score"]
        == decision[
            "base_production_score"
        ]
    )

    assert (
        decision["historical_evidence"][
            "reason"
        ]
        == "performance_evidence_unavailable"
    )

    print(
        "PASS: existing callers preserve "
        "the original production score."
    )

    # -------------------------------------------------
    # Evidence that is not strategy-ready is neutral.
    # -------------------------------------------------

    blocked = deepcopy(
        candidate
    )

    selector.rank(
        [blocked],
        performance=performance(
            ready=False,
            confidence=0.95,
            score=100,
        ),
    )

    blocked_decision = blocked[
        "production_selection"
    ]

    assert (
        blocked_decision[
            "historical_adjustment"
        ]
        == 0.0
    )

    assert (
        blocked_decision[
            "production_score"
        ]
        == blocked_decision[
            "base_production_score"
        ]
    )

    print(
        "PASS: weak channel evidence cannot "
        "change production ranking."
    )

    # -------------------------------------------------
    # Strong relevant history creates bounded bonus.
    # -------------------------------------------------

    supported = deepcopy(
        candidate
    )

    selector.rank(
        [supported],
        performance=performance(
            ready=True,
            confidence=1.0,
            score=100,
        ),
    )

    supported_decision = supported[
        "production_selection"
    ]

    assert (
        supported_decision[
            "historical_adjustment"
        ]
        == 8.0
    )

    assert (
        supported_decision[
            "production_score"
        ]
        == min(
            round(
                supported_decision[
                    "base_production_score"
                ]
                + 8.0,
                2,
            ),
            100.0,
        )
    )

    print(
        "PASS: strong relevant history adds "
        "the bounded maximum bonus."
    )

    # -------------------------------------------------
    # Weak relevant history creates bounded penalty.
    # -------------------------------------------------

    opposed = deepcopy(
        candidate
    )

    selector.rank(
        [opposed],
        performance=performance(
            ready=True,
            confidence=1.0,
            score=0,
        ),
    )

    opposed_decision = opposed[
        "production_selection"
    ]

    assert (
        opposed_decision[
            "historical_adjustment"
        ]
        == -8.0
    )

    assert (
        opposed_decision[
            "production_score"
        ]
        == max(
            round(
                opposed_decision[
                    "base_production_score"
                ]
                - 8.0,
                2,
            ),
            0.0,
        )
    )

    print(
        "PASS: weak relevant history adds "
        "the bounded maximum penalty."
    )

    # -------------------------------------------------
    # Historical evidence can change ordering, but only
    # through the bounded modifier.
    # -------------------------------------------------

    historically_supported = make_trend(
        "Customer returned shoes after "
        "wearing them for two years",
        viral=76,
    )

    higher_base_unrelated = make_trend(
        "Scientists reveal new battery technology",
        viral=82,
        category="Technology",
    )

    candidates = [
        higher_base_unrelated,
        historically_supported,
    ]

    ranked = selector.rank(
        candidates,
        performance=performance(
            ready=True,
            confidence=1.0,
            score=100,
        ),
    )

    supported_decision = (
        historically_supported[
            "production_selection"
        ]
    )

    unrelated_decision = (
        higher_base_unrelated[
            "production_selection"
        ]
    )

    assert (
        supported_decision[
            "historical_adjustment"
        ]
        > 0
    )

    assert (
        unrelated_decision[
            "historical_adjustment"
        ]
        == 0.0
    )

    assert (
        ranked[0]
        is historically_supported
    )

    print(
        "PASS: sufficiently strong relevant "
        "history can change candidate ordering."
    )

    # -------------------------------------------------
    # select() must use the same evidence path.
    # -------------------------------------------------

    select_candidates = [
        make_trend(
            "Scientists reveal new "
            "battery technology",
            viral=82,
            category="Technology",
        ),
        make_trend(
            "Customer returned shoes after "
            "wearing them for two years",
            viral=76,
        ),
    ]

    winner = selector.select(
        select_candidates,
        performance=performance(
            ready=True,
            confidence=1.0,
            score=100,
        ),
    )

    assert winner is not None

    assert (
        "Customer returned shoes"
        in winner["title"]
    )

    assert (
        winner[
            "production_selection"
        ]["selected"]
        is True
    )

    print(
        "PASS: select() uses historical "
        "evidence consistently with rank()."
    )

    print("=" * 72)
    print(
        "ALL PRODUCTION SELECTOR "
        "HISTORICAL TESTS PASSED"
    )
    print("=" * 72)


if __name__ == "__main__":
    main()
