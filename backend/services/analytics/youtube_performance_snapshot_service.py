"""Persistence service for YouTube performance snapshots."""

from __future__ import annotations

from datetime import (
    datetime,
    timezone,
)
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.youtube_performance_snapshot import (
    YoutubePerformanceSnapshotRecord,
)


class YoutubePerformanceSnapshotService:
    """Persist and query append-only YouTube performance observations."""

    @staticmethod
    def _utc_now() -> datetime:
        """Return naive UTC for SQLite DateTime consistency."""

        return datetime.now(
            timezone.utc
        ).replace(
            tzinfo=None
        )

    @staticmethod
    def _parse_datetime(
        value: Any,
    ) -> datetime | None:
        """Convert an ISO timestamp to naive UTC."""

        if isinstance(
            value,
            datetime,
        ):
            parsed = value

        else:
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
            return parsed

        return parsed.astimezone(
            timezone.utc
        ).replace(
            tzinfo=None
        )

    @staticmethod
    def _safe_count(
        value: Any,
    ) -> int:
        """Normalize provider counters to non-negative integers."""

        try:
            return max(
                int(
                    value or 0
                ),
                0,
            )
        except (
            TypeError,
            ValueError,
        ):
            return 0

    async def create_snapshot(
        self,
        session: AsyncSession,
        *,
        video: dict[str, Any],
        captured_at: datetime | None = None,
    ) -> YoutubePerformanceSnapshotRecord:
        """Append one immutable statistics observation."""

        video_id = str(
            video.get(
                "video_id",
                "",
            )
        ).strip()

        if not video_id:
            raise ValueError(
                "video.video_id cannot be empty."
            )

        channel_id = str(
            video.get(
                "channel_id",
                "",
            )
        ).strip()

        if not channel_id:
            raise ValueError(
                "video.channel_id cannot be empty."
            )

        capture_time = (
            captured_at
            if captured_at is not None
            else self._utc_now()
        )

        if capture_time.tzinfo is not None:
            capture_time = (
                capture_time
                .astimezone(
                    timezone.utc
                )
                .replace(
                    tzinfo=None
                )
            )

        snapshot = YoutubePerformanceSnapshotRecord(
            video_id=video_id,
            channel_id=channel_id,
            title=str(
                video.get(
                    "title",
                    "",
                )
            ).strip(),
            privacy_status=str(
                video.get(
                    "privacy_status",
                    "",
                )
            ).strip(),
            published_at=self._parse_datetime(
                video.get(
                    "published_at"
                )
            ),
            captured_at=capture_time,
            views=self._safe_count(
                video.get(
                    "views"
                )
            ),
            likes=self._safe_count(
                video.get(
                    "likes"
                )
            ),
            comments=self._safe_count(
                video.get(
                    "comments"
                )
            ),
        )

        session.add(
            snapshot
        )

        await session.commit()
        await session.refresh(
            snapshot
        )

        return snapshot

    async def create_snapshots(
        self,
        session: AsyncSession,
        *,
        videos: list[dict[str, Any]],
        captured_at: datetime | None = None,
    ) -> list[YoutubePerformanceSnapshotRecord]:
        """Append multiple observations using one capture timestamp."""

        if not videos:
            return []

        capture_time = (
            captured_at
            if captured_at is not None
            else self._utc_now()
        )

        snapshots: list[
            YoutubePerformanceSnapshotRecord
        ] = []

        for video in videos:
            video_id = str(
                video.get(
                    "video_id",
                    "",
                )
            ).strip()

            channel_id = str(
                video.get(
                    "channel_id",
                    "",
                )
            ).strip()

            if not video_id:
                raise ValueError(
                    "video.video_id cannot be empty."
                )

            if not channel_id:
                raise ValueError(
                    "video.channel_id cannot be empty."
                )

            normalized_capture = capture_time

            if (
                normalized_capture.tzinfo
                is not None
            ):
                normalized_capture = (
                    normalized_capture
                    .astimezone(
                        timezone.utc
                    )
                    .replace(
                        tzinfo=None
                    )
                )

            snapshots.append(
                YoutubePerformanceSnapshotRecord(
                    video_id=video_id,
                    channel_id=channel_id,
                    title=str(
                        video.get(
                            "title",
                            "",
                        )
                    ).strip(),
                    privacy_status=str(
                        video.get(
                            "privacy_status",
                            "",
                        )
                    ).strip(),
                    published_at=self._parse_datetime(
                        video.get(
                            "published_at"
                        )
                    ),
                    captured_at=normalized_capture,
                    views=self._safe_count(
                        video.get(
                            "views"
                        )
                    ),
                    likes=self._safe_count(
                        video.get(
                            "likes"
                        )
                    ),
                    comments=self._safe_count(
                        video.get(
                            "comments"
                        )
                    ),
                )
            )

        session.add_all(
            snapshots
        )

        await session.commit()

        for snapshot in snapshots:
            await session.refresh(
                snapshot
            )

        return snapshots

    async def list_for_video(
        self,
        session: AsyncSession,
        video_id: str,
    ) -> list[YoutubePerformanceSnapshotRecord]:
        """Return a video's full performance history oldest first."""

        clean_id = video_id.strip()

        if not clean_id:
            raise ValueError(
                "video_id cannot be empty."
            )

        statement = (
            select(
                YoutubePerformanceSnapshotRecord
            )
            .where(
                YoutubePerformanceSnapshotRecord.video_id
                == clean_id
            )
            .order_by(
                YoutubePerformanceSnapshotRecord
                .captured_at
                .asc()
            )
        )

        result = await session.execute(
            statement
        )

        return list(
            result.scalars().all()
        )

    async def list_latest_for_channel(
        self,
        session: AsyncSession,
        channel_id: str,
        *,
        limit: int = 100,
    ) -> list[YoutubePerformanceSnapshotRecord]:
        """Return recent channel observations newest first."""

        clean_id = channel_id.strip()

        if not clean_id:
            raise ValueError(
                "channel_id cannot be empty."
            )

        if limit <= 0:
            raise ValueError(
                "limit must be greater than zero."
            )

        statement = (
            select(
                YoutubePerformanceSnapshotRecord
            )
            .where(
                YoutubePerformanceSnapshotRecord.channel_id
                == clean_id
            )
            .order_by(
                YoutubePerformanceSnapshotRecord
                .captured_at
                .desc()
            )
            .limit(
                limit
            )
        )

        result = await session.execute(
            statement
        )

        return list(
            result.scalars().all()
        )
