"""YouTube channel performance collection."""

from __future__ import annotations

import asyncio
from datetime import (
    datetime,
    timezone,
)
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.analytics.youtube_performance_snapshot_service import (
    YoutubePerformanceSnapshotService,
)
from backend.services.providers.youtube_publisher import (
    YoutubePublisher,
)


class YoutubePerformanceCollector:
    """Collect YouTube statistics and persist immutable snapshots."""

    def __init__(
        self,
        *,
        publisher: YoutubePublisher | None = None,
        snapshot_service: (
            YoutubePerformanceSnapshotService
            | None
        ) = None,
    ) -> None:

        self.publisher = (
            publisher
            or YoutubePublisher()
        )

        self.snapshot_service = (
            snapshot_service
            or YoutubePerformanceSnapshotService()
        )

    @staticmethod
    def _utc_now() -> datetime:
        """Return naive UTC for SQLite consistency."""

        return datetime.now(
            timezone.utc
        ).replace(
            tzinfo=None
        )

    async def collect(
        self,
        session: AsyncSession,
        *,
        max_items: int = 50,
        captured_at: datetime | None = None,
    ) -> dict[str, Any]:
        """Collect recent authorized-channel performance."""

        if max_items <= 0:
            raise ValueError(
                "max_items must be positive."
            )

        upload_info = await asyncio.to_thread(
            self.publisher
            .get_recent_upload_video_ids,
            max_items=max_items,
        )

        channel_id = str(
            upload_info.get(
                "channel_id",
                "",
            )
        ).strip()

        video_ids = [
            str(video_id).strip()
            for video_id in (
                upload_info.get(
                    "video_ids",
                    [],
                )
                or []
            )
            if str(
                video_id
            ).strip()
        ]

        if not channel_id:
            raise ValueError(
                "Provider returned an empty channel ID."
            )

        collection_time = (
            captured_at
            if captured_at is not None
            else self._utc_now()
        )

        if not video_ids:
            return {
                "status": "completed",
                "channel_id": channel_id,
                "requested_video_count": 0,
                "collected_video_count": 0,
                "snapshot_count": 0,
                "captured_at": (
                    collection_time.isoformat()
                ),
                "video_ids": [],
            }

        statistics = await asyncio.to_thread(
            self.publisher.get_video_statistics,
            video_ids,
        )

        channel_statistics = [
            video
            for video in statistics
            if str(
                video.get(
                    "channel_id",
                    "",
                )
            ).strip()
            == channel_id
        ]

        snapshots = (
            await self.snapshot_service
            .create_snapshots(
                session,
                videos=channel_statistics,
                captured_at=collection_time,
            )
        )

        return {
            "status": "completed",
            "channel_id": channel_id,
            "requested_video_count": len(
                video_ids
            ),
            "collected_video_count": len(
                channel_statistics
            ),
            "snapshot_count": len(
                snapshots
            ),
            "captured_at": (
                collection_time.isoformat()
            ),
            "video_ids": [
                snapshot.video_id
                for snapshot in snapshots
            ],
        }
