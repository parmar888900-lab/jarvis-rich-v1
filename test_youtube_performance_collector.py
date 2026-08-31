"""Tests for YouTube performance collection."""

import asyncio
import tempfile
from datetime import (
    datetime,
    timezone,
)

from sqlalchemy.ext.asyncio import (
    async_sessionmaker,
    create_async_engine,
)

from backend.database import Base
from backend.models.youtube_performance_snapshot import (
    YoutubePerformanceSnapshotRecord,
)
from backend.services.analytics.youtube_performance_collector import (
    YoutubePerformanceCollector,
)
from backend.services.analytics.youtube_performance_snapshot_service import (
    YoutubePerformanceSnapshotService,
)


class FakePublisher:

    def __init__(self):
        self.discovery_calls = 0
        self.statistics_calls = []

    def get_recent_upload_video_ids(
        self,
        *,
        max_items=50,
    ):
        self.discovery_calls += 1

        assert max_items == 10

        return {
            "channel_id": "channel-123",
            "uploads_playlist_id": "uploads-123",
            "video_ids": [
                "video-1",
                "video-2",
            ],
        }

    def get_video_statistics(
        self,
        video_ids,
    ):
        self.statistics_calls.append(
            list(video_ids)
        )

        return [
            {
                "video_id": "video-1",
                "channel_id": "channel-123",
                "title": "First",
                "published_at": (
                    "2026-08-30T10:00:00Z"
                ),
                "privacy_status": "public",
                "views": 1000,
                "likes": 100,
                "comments": 20,
            },
            {
                "video_id": "video-2",
                "channel_id": "channel-123",
                "title": "Second",
                "published_at": (
                    "2026-08-30T11:00:00Z"
                ),
                "privacy_status": "public",
                "views": 500,
                "likes": 40,
                "comments": 5,
            },
            {
                # Must never be persisted.
                "video_id": "foreign-video",
                "channel_id": "foreign-channel",
                "title": "Foreign",
                "published_at": (
                    "2026-08-30T11:00:00Z"
                ),
                "privacy_status": "public",
                "views": 999999,
                "likes": 99999,
                "comments": 9999,
            },
        ]


class EmptyPublisher:

    def __init__(self):
        self.statistics_called = False

    def get_recent_upload_video_ids(
        self,
        *,
        max_items=50,
    ):
        return {
            "channel_id": "channel-empty",
            "uploads_playlist_id": "uploads-empty",
            "video_ids": [],
        }

    def get_video_statistics(
        self,
        video_ids,
    ):
        self.statistics_called = True
        raise AssertionError(
            "Statistics should not be requested "
            "when there are no uploads."
        )


async def main():
    print("=" * 72)
    print("YOUTUBE PERFORMANCE COLLECTOR TEST")
    print("=" * 72)

    with tempfile.TemporaryDirectory() as directory:

        engine = create_async_engine(
            "sqlite+aiosqlite:///"
            f"{directory}/collector.db"
        )

        session_factory = async_sessionmaker(
            engine,
            expire_on_commit=False,
        )

        async with engine.begin() as connection:
            await connection.run_sync(
                YoutubePerformanceSnapshotRecord
                .metadata
                .create_all
            )

        fake = FakePublisher()

        collector = YoutubePerformanceCollector(
            publisher=fake,
            snapshot_service=(
                YoutubePerformanceSnapshotService()
            ),
        )

        captured_at = datetime(
            2026,
            8,
            30,
            18,
            0,
            tzinfo=timezone.utc,
        )

        async with session_factory() as session:

            result = await collector.collect(
                session,
                max_items=10,
                captured_at=captured_at,
            )

            assert (
                result["status"]
                == "completed"
            )

            assert (
                result["channel_id"]
                == "channel-123"
            )

            assert (
                result[
                    "requested_video_count"
                ]
                == 2
            )

            assert (
                result[
                    "collected_video_count"
                ]
                == 2
            )

            assert (
                result["snapshot_count"]
                == 2
            )

            assert result["video_ids"] == [
                "video-1",
                "video-2",
            ]

            assert (
                fake.statistics_calls
                == [
                    [
                        "video-1",
                        "video-2",
                    ]
                ]
            )

            print(
                "PASS: collector discovers uploads "
                "and requests their statistics."
            )

            history = (
                await collector
                .snapshot_service
                .list_latest_for_channel(
                    session,
                    "channel-123",
                    limit=10,
                )
            )

            assert len(history) == 2

            assert {
                item.video_id
                for item in history
            } == {
                "video-1",
                "video-2",
            }

            assert all(
                item.channel_id
                == "channel-123"
                for item in history
            )

            print(
                "PASS: collected statistics are "
                "persisted as channel snapshots."
            )

            assert not any(
                item.video_id
                == "foreign-video"
                for item in history
            )

            print(
                "PASS: foreign-channel provider "
                "records are rejected."
            )

        await engine.dispose()

    with tempfile.TemporaryDirectory() as directory:

        engine = create_async_engine(
            "sqlite+aiosqlite:///"
            f"{directory}/empty.db"
        )

        session_factory = async_sessionmaker(
            engine,
            expire_on_commit=False,
        )

        async with engine.begin() as connection:
            await connection.run_sync(
                YoutubePerformanceSnapshotRecord
                .metadata
                .create_all
            )

        empty = EmptyPublisher()

        collector = YoutubePerformanceCollector(
            publisher=empty,
        )

        async with session_factory() as session:

            result = await collector.collect(
                session,
                max_items=10,
                captured_at=captured_at,
            )

            assert (
                result["snapshot_count"]
                == 0
            )

            assert (
                result[
                    "requested_video_count"
                ]
                == 0
            )

            assert not empty.statistics_called

            print(
                "PASS: empty channels complete "
                "without unnecessary statistics calls."
            )

        await engine.dispose()

    try:
        async with session_factory() as session:
            await collector.collect(
                session,
                max_items=0,
            )
    except ValueError:
        pass
    else:
        raise AssertionError(
            "Invalid max_items was accepted."
        )

    print(
        "PASS: invalid collection limits "
        "are rejected."
    )

    print("=" * 72)
    print(
        "ALL YOUTUBE PERFORMANCE COLLECTOR "
        "TESTS PASSED"
    )
    print("=" * 72)


if __name__ == "__main__":
    asyncio.run(
        main()
    )
