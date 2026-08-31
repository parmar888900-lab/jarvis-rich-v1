"""Build strategy evidence from persisted YouTube performance snapshots."""

from __future__ import annotations

from datetime import timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.analytics.youtube_performance import (
    YoutubePerformanceAnalyzer,
)
from backend.services.analytics.youtube_performance_snapshot_service import (
    YoutubePerformanceSnapshotService,
)


class YoutubePerformanceEvidenceService:
    """
    Build confidence-gated channel performance evidence.

    Snapshot persistence is append-only, but strategy analysis must use
    only the newest observation for each video. Repeated collection of
    the same video must never inflate sample size or audience evidence.
    """

    def __init__(
        self,
        *,
        snapshot_service: (
            YoutubePerformanceSnapshotService
            | None
        ) = None,
        analyzer: YoutubePerformanceAnalyzer | None = None,
    ) -> None:
        self.snapshot_service = (
            snapshot_service
            or YoutubePerformanceSnapshotService()
        )

        self.analyzer = (
            analyzer
            or YoutubePerformanceAnalyzer()
        )

    @staticmethod
    def _datetime_text(value: Any) -> str:
        """Normalize a stored datetime to an ISO-8601 UTC string."""

        if value is None:
            return ""

        if not hasattr(value, "isoformat"):
            return str(value).strip()

        if value.tzinfo is None:
            value = value.replace(
                tzinfo=timezone.utc
            )
        else:
            value = value.astimezone(
                timezone.utc
            )

        return value.isoformat()

    @classmethod
    def _snapshot_to_video(
        cls,
        snapshot: Any,
    ) -> dict[str, Any]:
        """Convert one ORM snapshot into analyzer input."""

        return {
            "video_id": str(
                snapshot.video_id
            ).strip(),
            "channel_id": str(
                snapshot.channel_id
            ).strip(),
            "title": str(
                snapshot.title or ""
            ).strip(),
            "privacy_status": str(
                snapshot.privacy_status or ""
            ).strip(),
            "published_at": cls._datetime_text(
                snapshot.published_at
            ),
            "views": max(
                int(snapshot.views or 0),
                0,
            ),
            "likes": max(
                int(snapshot.likes or 0),
                0,
            ),
            "comments": max(
                int(snapshot.comments or 0),
                0,
            ),
        }

    async def build(
        self,
        session: AsyncSession,
        channel_id: str,
        *,
        snapshot_limit: int = 500,
    ) -> dict[str, Any]:
        """
        Build channel strategy evidence from latest unique video snapshots.

        list_latest_for_channel() returns newest snapshots first, so the
        first occurrence of each video ID is its newest observation.
        """

        clean_channel_id = str(
            channel_id or ""
        ).strip()

        if not clean_channel_id:
            raise ValueError(
                "channel_id cannot be empty."
            )

        if snapshot_limit <= 0:
            raise ValueError(
                "snapshot_limit must be greater than zero."
            )

        snapshots = (
            await self.snapshot_service
            .list_latest_for_channel(
                session,
                clean_channel_id,
                limit=snapshot_limit,
            )
        )

        latest_by_video: dict[str, Any] = {}

        for snapshot in snapshots:
            video_id = str(
                snapshot.video_id or ""
            ).strip()

            if not video_id:
                continue

            if video_id in latest_by_video:
                continue

            latest_by_video[
                video_id
            ] = snapshot

        videos = [
            self._snapshot_to_video(
                snapshot
            )
            for snapshot in latest_by_video.values()
        ]

        evidence = self.analyzer.analyze(
            videos
        )

        return {
            **evidence,
            "channel_id": clean_channel_id,
            "snapshot_count": len(
                snapshots
            ),
            "unique_video_count": len(
                videos
            ),
        }
