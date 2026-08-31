"""Regression tests for YouTube performance analysis."""

from datetime import (
    datetime,
    timezone,
)

from backend.services.analytics.youtube_performance import (
    YoutubePerformanceAnalyzer,
)


def make_video(
    *,
    video_id,
    published_at,
    views,
    likes,
    comments,
):
    return {
        "video_id": video_id,
        "channel_id": "channel-123",
        "title": video_id,
        "published_at": published_at,
        "privacy_status": "public",
        "views": views,
        "likes": likes,
        "comments": comments,
    }


def main():
    print("=" * 72)
    print(
        "YOUTUBE PERFORMANCE ANALYZER TEST"
    )
    print("=" * 72)

    analyzer = YoutubePerformanceAnalyzer()

    now = datetime(
        2026,
        8,
        30,
        18,
        0,
        0,
        tzinfo=timezone.utc,
    )

    videos = [
        make_video(
            video_id="strong",
            published_at=(
                "2026-08-30T06:00:00Z"
            ),
            views=12000,
            likes=1200,
            comments=240,
        ),
        make_video(
            video_id="baseline",
            published_at=(
                "2026-08-29T18:00:00Z"
            ),
            views=12000,
            likes=600,
            comments=120,
        ),
        make_video(
            video_id="weak",
            published_at=(
                "2026-08-28T18:00:00Z"
            ),
            views=6000,
            likes=120,
            comments=30,
        ),
    ]

    result = analyzer.analyze(
        videos,
        collected_at=now,
    )

    assert result["video_count"] == 3

    assert result["confidence"] == (
        3 / 20
    )

    by_id = {
        video["video_id"]: video
        for video in result["videos"]
    }

    assert (
        by_id["strong"]["age_hours"]
        == 12.0
    )

    assert (
        by_id["strong"][
            "views_per_hour"
        ]
        == 1000.0
    )

    assert (
        by_id["baseline"][
            "views_per_hour"
        ]
        == 500.0
    )

    assert (
        by_id["weak"][
            "views_per_hour"
        ]
        == 125.0
    )

    assert (
        by_id["strong"][
            "performance_score"
        ]
        > by_id["baseline"][
            "performance_score"
        ]
        > by_id["weak"][
            "performance_score"
        ]
    )

    print(
        "PASS: video age is normalized."
    )

    print(
        "PASS: views-per-hour prevents "
        "older videos from receiving an "
        "automatic advantage."
    )

    print(
        "PASS: engagement contributes to "
        "relative performance."
    )

    print(
        "PASS: stronger relative videos "
        "receive higher performance scores."
    )

    assert (
        result["baseline_views_per_hour"]
        == 500.0
    )

    print(
        "PASS: channel baseline uses median "
        "performance rather than an "
        "outlier-sensitive mean."
    )

    # -------------------------------------------------
    # Small samples must have low confidence.
    # -------------------------------------------------

    one_video = analyzer.analyze(
        [
            make_video(
                video_id="single",
                published_at=(
                    "2026-08-30T17:00:00Z"
                ),
                views=1000,
                likes=100,
                comments=10,
            )
        ],
        collected_at=now,
    )

    assert (
        one_video["confidence"]
        == 0.05
    )

    print(
        "PASS: one-video sample receives "
        "only 5% confidence."
    )

    # -------------------------------------------------
    # Twenty samples should reach full confidence.
    # -------------------------------------------------

    twenty = analyzer.analyze(
        [
            make_video(
                video_id=f"video-{index}",
                published_at=(
                    "2026-08-29T18:00:00Z"
                ),
                views=1000 + index,
                likes=100,
                comments=10,
            )
            for index in range(20)
        ],
        collected_at=now,
    )

    assert twenty["confidence"] == 1.0

    print(
        "PASS: confidence reaches 100% "
        "at twenty observations."
    )

    # -------------------------------------------------
    # Zero-view video must not divide by zero.
    # -------------------------------------------------

    zero = analyzer.normalize_video(
        make_video(
            video_id="zero",
            published_at=(
                "2026-08-30T17:00:00Z"
            ),
            views=0,
            likes=0,
            comments=0,
        ),
        collected_at=now,
    )

    assert zero["like_rate"] == 0.0
    assert zero["comment_rate"] == 0.0
    assert zero["engagement_rate"] == 0.0

    print(
        "PASS: zero-view videos are "
        "handled safely."
    )

    # -------------------------------------------------
    # Missing publication time is safe.
    # -------------------------------------------------

    missing_time = (
        analyzer.normalize_video(
            make_video(
                video_id="missing-time",
                published_at="",
                views=100,
                likes=10,
                comments=1,
            ),
            collected_at=now,
        )
    )

    assert (
        missing_time["age_hours"]
        is None
    )

    assert (
        missing_time["views_per_hour"]
        == 0.0
    )

    print(
        "PASS: missing publication "
        "timestamps fail closed."
    )

    empty = analyzer.analyze(
        [],
        collected_at=now,
    )

    assert empty == {
        "video_count": 0,
        "source_video_count": 0,
        "excluded_video_count": 0,
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
        "PASS: empty channel history "
        "returns a stable zero-data result."
    )

    print("=" * 72)
    print(
        "ALL YOUTUBE PERFORMANCE "
        "ANALYZER TESTS PASSED"
    )
    print("=" * 72)


if __name__ == "__main__":
    main()
