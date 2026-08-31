"""YouTube channel performance analysis."""

from __future__ import annotations

import math
from datetime import (
    datetime,
    timezone,
)
from statistics import median
from typing import Any


class YoutubePerformanceAnalyzer:
    """Normalize YouTube video performance across video age."""

    MIN_AGE_HOURS = 1.0
    CONFIDENCE_SAMPLE_TARGET = 20

    @staticmethod
    def _parse_datetime(
        value: str,
    ) -> datetime | None:
        """Parse an ISO-8601 YouTube timestamp."""

        clean = str(
            value or ""
        ).strip()

        if not clean:
            return None

        try:
            parsed = datetime.fromisoformat(
                clean.replace(
                    "Z",
                    "+00:00",
                )
            )
        except ValueError:
            return None

        if parsed.tzinfo is None:
            parsed = parsed.replace(
                tzinfo=timezone.utc
            )

        return parsed.astimezone(
            timezone.utc
        )

    @staticmethod
    def _bounded_rate(
        numerator: int,
        denominator: int,
    ) -> float:
        """Return a safe non-negative ratio."""

        if denominator <= 0:
            return 0.0

        return max(
            float(numerator)
            / float(denominator),
            0.0,
        )

    def normalize_video(
        self,
        video: dict[str, Any],
        *,
        collected_at: datetime | None = None,
    ) -> dict[str, Any]:
        """Calculate age-normalized metrics for one video."""

        now = (
            collected_at
            if collected_at is not None
            else datetime.now(
                timezone.utc
            )
        )

        if now.tzinfo is None:
            now = now.replace(
                tzinfo=timezone.utc
            )
        else:
            now = now.astimezone(
                timezone.utc
            )

        published = self._parse_datetime(
            str(
                video.get(
                    "published_at",
                    "",
                )
            )
        )

        age_hours: float | None = None

        if published is not None:
            age_seconds = (
                now - published
            ).total_seconds()

            age_hours = max(
                age_seconds / 3600.0,
                0.0,
            )

        views = max(
            int(
                video.get(
                    "views",
                    0,
                )
                or 0
            ),
            0,
        )

        likes = max(
            int(
                video.get(
                    "likes",
                    0,
                )
                or 0
            ),
            0,
        )

        comments = max(
            int(
                video.get(
                    "comments",
                    0,
                )
                or 0
            ),
            0,
        )

        if age_hours is None:
            views_per_hour = 0.0
        else:
            views_per_hour = (
                float(views)
                / max(
                    age_hours,
                    self.MIN_AGE_HOURS,
                )
            )

        like_rate = self._bounded_rate(
            likes,
            views,
        )

        comment_rate = self._bounded_rate(
            comments,
            views,
        )

        engagement_rate = (
            like_rate
            + comment_rate
        )

        return {
            **video,
            "collected_at": (
                now.isoformat()
            ),
            "age_hours": (
                round(
                    age_hours,
                    4,
                )
                if age_hours is not None
                else None
            ),
            "views_per_hour": round(
                views_per_hour,
                4,
            ),
            "like_rate": round(
                like_rate,
                6,
            ),
            "comment_rate": round(
                comment_rate,
                6,
            ),
            "engagement_rate": round(
                engagement_rate,
                6,
            ),
        }

    def analyze(
        self,
        videos: list[dict[str, Any]],
        *,
        collected_at: datetime | None = None,
    ) -> dict[str, Any]:
        """Analyze video performance relative to the channel baseline."""

        normalized = [
            self.normalize_video(
                video,
                collected_at=collected_at,
            )
            for video in videos
        ]

        if not normalized:
            return {
                "video_count": 0,
                "confidence": 0.0,
                "baseline_views_per_hour": 0.0,
                "baseline_engagement_rate": 0.0,
                "videos": [],
            }

        view_rates = [
            float(
                video["views_per_hour"]
            )
            for video in normalized
        ]

        engagement_rates = [
            float(
                video["engagement_rate"]
            )
            for video in normalized
        ]

        baseline_views = float(
            median(
                view_rates
            )
        )

        baseline_engagement = float(
            median(
                engagement_rates
            )
        )

        confidence = min(
            len(normalized)
            / float(
                self.CONFIDENCE_SAMPLE_TARGET
            ),
            1.0,
        )

        analyzed: list[dict[str, Any]] = []

        for video in normalized:
            views_per_hour = float(
                video[
                    "views_per_hour"
                ]
            )

            engagement_rate = float(
                video[
                    "engagement_rate"
                ]
            )

            if baseline_views > 0:
                relative_views = (
                    views_per_hour
                    / baseline_views
                )
            else:
                relative_views = (
                    1.0
                    if views_per_hour > 0
                    else 0.0
                )

            if baseline_engagement > 0:
                relative_engagement = (
                    engagement_rate
                    / baseline_engagement
                )
            else:
                relative_engagement = (
                    1.0
                    if engagement_rate > 0
                    else 0.0
                )

            view_score = (
                50.0
                + 25.0
                * math.tanh(
                    math.log(
                        max(
                            relative_views,
                            0.01,
                        )
                    )
                )
            )

            engagement_score = (
                50.0
                + 25.0
                * math.tanh(
                    math.log(
                        max(
                            relative_engagement,
                            0.01,
                        )
                    )
                )
            )

            raw_score = (
                view_score * 0.75
                + engagement_score * 0.25
            )

            performance_score = min(
                max(
                    raw_score,
                    0.0,
                ),
                100.0,
            )

            analyzed.append(
                {
                    **video,
                    "relative_views": round(
                        relative_views,
                        4,
                    ),
                    "relative_engagement": round(
                        relative_engagement,
                        4,
                    ),
                    "performance_score": round(
                        performance_score,
                        2,
                    ),
                }
            )

        analyzed.sort(
            key=lambda video: (
                video[
                    "performance_score"
                ],
                video[
                    "views_per_hour"
                ],
            ),
            reverse=True,
        )

        return {
            "video_count": len(
                analyzed
            ),
            "confidence": round(
                confidence,
                4,
            ),
            "baseline_views_per_hour": round(
                baseline_views,
                4,
            ),
            "baseline_engagement_rate": round(
                baseline_engagement,
                6,
            ),
            "videos": analyzed,
        }
