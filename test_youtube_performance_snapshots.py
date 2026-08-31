"""Tests for persistent YouTube performance snapshots."""

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
from backend.services.analytics.youtube_performance_snapshot_service import (
    YoutubePerformanceSnapshotService,
)


async def main():
    print("=" * 72)
    print(
        "YOUTUBE PERFORMANCE SNAPSHOT "
        "PERSISTENCE TEST"
    )
    print("=" * 72)

    with tempfile.TemporaryDirectory() as directory:
        database_path = (
            f"{directory}/analytics.db"
        )

        engine = create_async_engine(
            "sqlite+aiosqlite:///"
            f"{database_path}"
        )

        session_factory = (
            async_sessionmaker(
                engine,
                expire_on_commit=False,
            )
        )

        async with engine.begin() as connection:
            await connection.run_sync(
                YoutubePerformanceSnapshotRecord
                .metadata
                .create_all
            )

        service = (
            YoutubePerformanceSnapshotService()
        )

        first_time = datetime(
            2026,
            8,
            30,
            12,
            0,
            0,
            tzinfo=timezone.utc,
        )

        second_time = datetime(
            2026,
            8,
            30,
            18,
            0,
            0,
            tzinfo=timezone.utc,
        )

        first_video = {
            "video_id": "video-001",
            "channel_id": "channel-123",
            "title": "Jarvis Analytics Test",
            "published_at": (
                "2026-08-30T10:00:00Z"
            ),
            "privacy_status": "public",
            "views": 100,
            "likes": 10,
            "comments": 2,
        }

        second_video = {
            **first_video,
            "views": 900,
            "likes": 80,
            "comments": 14,
        }

        async with session_factory() as session:
            first = await service.create_snapshot(
                session,
                video=first_video,
                captured_at=first_time,
            )

            second = await service.create_snapshot(
                session,
                video=second_video,
                captured_at=second_time,
            )

            assert first.id != second.id

            assert (
                first.video_id
                == second.video_id
                == "video-001"
            )

            assert first.views == 100
            assert second.views == 900

            print(
                "PASS: repeated polls create "
                "append-only snapshots."
            )

            history = await service.list_for_video(
                session,
                "video-001",
            )

            assert len(history) == 2

            assert [
                item.views
                for item in history
            ] == [
                100,
                900,
            ]

            assert (
                history[0].captured_at
                < history[1].captured_at
            )

            print(
                "PASS: full video history is "
                "returned chronologically."
            )

            assert (
                history[0].published_at
                == datetime(
                    2026,
                    8,
                    30,
                    10,
                    0,
                    0,
                )
            )

            assert (
                history[0].captured_at
                == datetime(
                    2026,
                    8,
                    30,
                    12,
                    0,
                    0,
                )
            )

            print(
                "PASS: timezone-aware provider "
                "timestamps are stored as naive UTC."
            )

            batch_time = datetime(
                2026,
                8,
                31,
                0,
                0,
                0,
                tzinfo=timezone.utc,
            )

            batch = await service.create_snapshots(
                session,
                videos=[
                    {
                        "video_id": "video-001",
                        "channel_id": "channel-123",
                        "title": "Jarvis Analytics Test",
                        "published_at": (
                            "2026-08-30T10:00:00Z"
                        ),
                        "privacy_status": "public",
                        "views": 1500,
                        "likes": 120,
                        "comments": 20,
                    },
                    {
                        "video_id": "video-002",
                        "channel_id": "channel-123",
                        "title": "Second Video",
                        "published_at": (
                            "2026-08-30T20:00:00Z"
                        ),
                        "privacy_status": "public",
                        "views": 300,
                        "likes": 30,
                        "comments": 5,
                    },
                ],
                captured_at=batch_time,
            )

            assert len(batch) == 2

            assert (
                batch[0].captured_at
                == batch[1].captured_at
            )

            print(
                "PASS: batch collection uses "
                "one consistent capture timestamp."
            )

            recent = (
                await service.list_latest_for_channel(
                    session,
                    "channel-123",
                    limit=10,
                )
            )

            assert len(recent) == 4

            assert (
                recent[0].captured_at
                >= recent[-1].captured_at
            )

            print(
                "PASS: channel snapshots can "
                "be queried newest first."
            )

            malformed = await service.create_snapshot(
                session,
                video={
                    "video_id": "video-bad",
                    "channel_id": "channel-123",
                    "title": "Malformed counts",
                    "published_at": "invalid",
                    "privacy_status": "private",
                    "views": "invalid",
                    "likes": None,
                    "comments": -8,
                },
                captured_at=batch_time,
            )

            assert malformed.views == 0
            assert malformed.likes == 0
            assert malformed.comments == 0
            assert malformed.published_at is None

            print(
                "PASS: malformed provider data "
                "fails closed safely."
            )

            try:
                await service.create_snapshot(
                    session,
                    video={
                        "video_id": "",
                        "channel_id": "channel-123",
                    },
                )
            except ValueError:
                pass
            else:
                raise AssertionError(
                    "Empty video ID was accepted."
                )

            print(
                "PASS: empty video IDs are rejected."
            )

            try:
                await service.create_snapshot(
                    session,
                    video={
                        "video_id": "video-003",
                        "channel_id": "",
                    },
                )
            except ValueError:
                pass
            else:
                raise AssertionError(
                    "Empty channel ID was accepted."
                )

            print(
                "PASS: empty channel IDs are rejected."
            )

        await engine.dispose()

    print("=" * 72)
    print(
        "ALL YOUTUBE PERFORMANCE SNAPSHOT "
        "PERSISTENCE TESTS PASSED"
    )
    print("=" * 72)


if __name__ == "__main__":
    asyncio.run(
        main()
    )
