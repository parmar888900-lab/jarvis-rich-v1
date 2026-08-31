"""Tests for historical YouTube performance intelligence."""

from backend.services.analytics.youtube_historical_intelligence import (
    YoutubeHistoricalIntelligence,
)


def historical_video(
    video_id,
    title,
    performance_score,
    *,
    category="",
):
    result = {
        "video_id": video_id,
        "title": title,
        "performance_score": (
            performance_score
        ),
    }

    if category:
        result["category"] = category

    return result


def performance(
    videos,
    *,
    ready=True,
    confidence=1.0,
):
    return {
        "strategy_ready": ready,
        "confidence": confidence,
        "videos": videos,
    }


def main():
    print("=" * 72)
    print(
        "YOUTUBE HISTORICAL INTELLIGENCE TEST"
    )
    print("=" * 72)

    intelligence = (
        YoutubeHistoricalIntelligence()
    )

    candidate = {
        "title": (
            "Customer returned shoes after "
            "wearing them for years"
        ),
        "category": "Stories",
    }

    # -------------------------------------------------
    # Evidence gate must override everything.
    # -------------------------------------------------

    blocked = intelligence.evaluate(
        candidate,
        performance(
            [
                historical_video(
                    "huge",
                    (
                        "Customer returned shoes "
                        "after two years"
                    ),
                    100,
                )
            ],
            ready=False,
            confidence=0.95,
        ),
    )

    assert (
        blocked["historical_score"]
        == 50.0
    )
    assert blocked["adjustment"] == 0.0
    assert blocked["match_count"] == 0
    assert (
        blocked["reason"]
        == "performance_evidence_not_ready"
    )

    print(
        "PASS: strategy gate prevents weak "
        "history from affecting production."
    )

    # -------------------------------------------------
    # Relevant strong history should help.
    # -------------------------------------------------

    strong = intelligence.evaluate(
        candidate,
        performance(
            [
                historical_video(
                    "strong-1",
                    (
                        "Customer tried returning "
                        "shoes after wearing them "
                        "for two years"
                    ),
                    90,
                ),
                historical_video(
                    "unrelated",
                    (
                        "Scientists discover new "
                        "battery technology"
                    ),
                    100,
                ),
            ],
            confidence=1.0,
        ),
    )

    assert strong["strategy_ready"] is True
    assert strong["match_count"] == 1
    assert strong["historical_score"] == 90.0
    assert strong["adjustment"] > 0
    assert strong["adjustment"] <= 8.0

    print(
        "PASS: strong relevant historical "
        "performance creates a bounded bonus."
    )

    # -------------------------------------------------
    # Relevant weak history should penalize.
    # -------------------------------------------------

    weak = intelligence.evaluate(
        candidate,
        performance(
            [
                historical_video(
                    "weak-1",
                    (
                        "Customer returned shoes "
                        "after wearing them"
                    ),
                    10,
                )
            ],
            confidence=1.0,
        ),
    )

    assert weak["historical_score"] == 10.0
    assert weak["adjustment"] < 0
    assert weak["adjustment"] >= -8.0

    print(
        "PASS: weak relevant historical "
        "performance creates a bounded penalty."
    )

    # -------------------------------------------------
    # Unrelated history must remain neutral.
    # -------------------------------------------------

    unrelated = intelligence.evaluate(
        candidate,
        performance(
            [
                historical_video(
                    "science",
                    (
                        "Scientists discover "
                        "new battery technology"
                    ),
                    100,
                )
            ],
            confidence=1.0,
        ),
    )

    assert unrelated["historical_score"] == 50.0
    assert unrelated["adjustment"] == 0.0
    assert unrelated["match_count"] == 0

    print(
        "PASS: unrelated high-performing "
        "videos do not affect the candidate."
    )

    # -------------------------------------------------
    # Confidence must proportionally limit influence.
    # -------------------------------------------------

    full = intelligence.evaluate(
        candidate,
        performance(
            [
                historical_video(
                    "strong",
                    (
                        "Customer returned shoes "
                        "after wearing them"
                    ),
                    100,
                )
            ],
            confidence=1.0,
        ),
    )

    quarter = intelligence.evaluate(
        candidate,
        performance(
            [
                historical_video(
                    "strong",
                    (
                        "Customer returned shoes "
                        "after wearing them"
                    ),
                    100,
                )
            ],
            confidence=0.25,
        ),
    )

    assert full["adjustment"] == 8.0
    assert quarter["adjustment"] == 2.0

    print(
        "PASS: evidence confidence scales "
        "historical influence."
    )

    # -------------------------------------------------
    # Category can support matching only when both
    # historical and candidate metadata actually exist.
    # -------------------------------------------------

    category_match = intelligence.evaluate(
        {
            "title": (
                "Completely different wording"
            ),
            "knowledge": {
                "category": "Technology",
            },
        },
        performance(
            [
                historical_video(
                    "technology",
                    (
                        "AI systems improve "
                        "rapidly"
                    ),
                    80,
                    category="Technology",
                )
            ],
            confidence=1.0,
        ),
    )

    assert (
        category_match["match_count"]
        == 1
    )
    assert (
        category_match["matches"][0][
            "category_match"
        ]
        is True
    )
    assert (
        category_match["adjustment"]
        > 0
    )

    print(
        "PASS: real category metadata can "
        "support historical matching."
    )

    # -------------------------------------------------
    # Missing evidence fails neutral.
    # -------------------------------------------------

    missing = intelligence.evaluate(
        candidate,
        None,
    )

    assert missing == {
        "strategy_ready": False,
        "historical_score": 50.0,
        "confidence": 0.0,
        "adjustment": 0.0,
        "match_count": 0,
        "matches": [],
        "reason": (
            "performance_evidence_unavailable"
        ),
    }

    print(
        "PASS: missing performance evidence "
        "fails neutral."
    )

    print("=" * 72)
    print(
        "ALL YOUTUBE HISTORICAL "
        "INTELLIGENCE TESTS PASSED"
    )
    print("=" * 72)


if __name__ == "__main__":
    main()
