"""Evidence-gate tests for YouTube performance analysis."""

from datetime import (
    datetime,
    timezone,
)

from backend.services.analytics.youtube_performance import (
    YoutubePerformanceAnalyzer,
)


def video(
    video_id,
    *,
    privacy="public",
    views=0,
    likes=0,
    comments=0,
    published_at="2026-08-29T18:00:00Z",
):
    return {
        "video_id": video_id,
        "channel_id": "channel-123",
        "title": video_id,
        "published_at": published_at,
        "privacy_status": privacy,
        "views": views,
        "likes": likes,
        "comments": comments,
    }


def main():
    print("=" * 72)
    print("YOUTUBE PERFORMANCE EVIDENCE GATE TEST")
    print("=" * 72)

    analyzer = YoutubePerformanceAnalyzer()

    now = datetime(
        2026,
        8,
        30,
        18,
        0,
        tzinfo=timezone.utc,
    )

    # ---------------------------------------------------------
    # Private and unlisted content cannot become audience
    # evidence even when authenticated statistics are visible.
    # ---------------------------------------------------------

    result = analyzer.analyze(
        [
            video(
                "public",
                views=120,
                likes=12,
                comments=2,
            ),
            video(
                "private",
                privacy="private",
                views=1000000,
                likes=100000,
                comments=10000,
            ),
            video(
                "unlisted",
                privacy="unlisted",
                views=500000,
                likes=50000,
                comments=5000,
            ),
        ],
        collected_at=now,
    )

    assert result["source_video_count"] == 3
    assert result["video_count"] == 1
    assert result["excluded_video_count"] == 2

    assert [
        item["video_id"]
        for item in result["videos"]
    ] == [
        "public"
    ]

    assert result["total_views"] == 120

    print(
        "PASS: private and unlisted videos "
        "cannot influence audience evidence."
    )

    # ---------------------------------------------------------
    # Missing publication time cannot produce age-normalized
    # strategy evidence.
    # ---------------------------------------------------------

    result = analyzer.analyze(
        [
            video(
                "valid",
                views=100,
            ),
            video(
                "missing-time",
                views=100000,
                published_at="",
            ),
        ],
        collected_at=now,
    )

    assert result["video_count"] == 1
    assert result["excluded_video_count"] == 1
    assert result["total_views"] == 100

    print(
        "PASS: videos without valid publication "
        "time fail closed."
    )

    # ---------------------------------------------------------
    # Low-view channels must not obtain strong confidence just
    # because several videos exist.
    # ---------------------------------------------------------

    weak = analyzer.analyze(
        [
            video(
                f"weak-{index}",
                views=1,
            )
            for index in range(10)
        ],
        collected_at=now,
    )

    assert weak["video_count"] == 10
    assert weak["total_views"] == 10

    assert weak["sample_confidence"] == 0.5
    assert weak["audience_confidence"] == 0.1
    assert weak["confidence"] == 0.05

    assert weak["strategy_ready"] is False

    print(
        "PASS: many near-zero-view videos "
        "remain weak strategy evidence."
    )

    # ---------------------------------------------------------
    # Audience evidence and sample evidence are independent.
    # One viral observation cannot produce high confidence.
    # ---------------------------------------------------------

    single = analyzer.analyze(
        [
            video(
                "single-hit",
                views=100000,
                likes=10000,
                comments=1000,
            )
        ],
        collected_at=now,
    )

    assert single["sample_confidence"] == 0.05
    assert single["audience_confidence"] == 1.0
    assert single["confidence"] == 0.05
    assert single["strategy_ready"] is False

    print(
        "PASS: one high-view video cannot "
        "dominate channel strategy."
    )

    # ---------------------------------------------------------
    # Sufficient public observations can activate the strategy
    # evidence gate while confidence remains sample-bounded.
    # ---------------------------------------------------------

    ready = analyzer.analyze(
        [
            video(
                "ready-1",
                views=60,
            ),
            video(
                "ready-2",
                views=60,
            ),
        ],
        collected_at=now,
    )

    assert ready["total_views"] == 120
    assert ready["sample_confidence"] == 0.1
    assert ready["audience_confidence"] == 1.0
    assert ready["confidence"] == 0.1
    assert ready["strategy_ready"] is True

    print(
        "PASS: strategy readiness requires "
        "multiple public videos and minimum "
        "audience observations."
    )

    # ---------------------------------------------------------
    # No eligible evidence returns an explicit zero state.
    # ---------------------------------------------------------

    none = analyzer.analyze(
        [
            video(
                "private-only",
                privacy="private",
                views=1000,
            )
        ],
        collected_at=now,
    )

    assert none == {
        "video_count": 0,
        "source_video_count": 1,
        "excluded_video_count": 1,
        "total_views": 0,
        "sample_confidence": 0.0,
        "audience_confidence": 0.0,
        "confidence": 0.0,
        "strategy_ready": False,
        "baseline_views_per_hour": 0.0,
        "baseline_engagement_rate": 0.0,
        "videos": [],
    }

    print(
        "PASS: no eligible public evidence "
        "returns a stable fail-closed result."
    )

    print("=" * 72)
    print(
        "ALL YOUTUBE PERFORMANCE EVIDENCE "
        "GATE TESTS PASSED"
    )
    print("=" * 72)


if __name__ == "__main__":
    main()
