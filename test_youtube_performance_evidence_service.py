import asyncio
import tempfile
from datetime import (
    datetime,
    timedelta,
    timezone,
)

from sqlalchemy.ext.asyncio import (
    async_sessionmaker,
    create_async_engine,
)

from backend.models.youtube_performance_snapshot import (
    YoutubePerformanceSnapshotRecord,
)
from backend.services.analytics.youtube_performance_evidence_service import (
    YoutubePerformanceEvidenceService,
)
from backend.services.analytics.youtube_performance_snapshot_service import (
    YoutubePerformanceSnapshotService,
)


async def main():
    print("=" * 72)
    print("YOUTUBE PERFORMANCE EVIDENCE SERVICE TEST")
    print("=" * 72)

    with tempfile.TemporaryDirectory() as directory:
        engine = create_async_engine(
            "sqlite+aiosqlite:///"
            f"{directory}/evidence.db"
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

        snapshot_service = (
            YoutubePerformanceSnapshotService()
        )

        evidence_service = (
            YoutubePerformanceEvidenceService(
                snapshot_service=snapshot_service
            )
        )

        now = datetime.now(
            timezone.utc
        )

        videos_first = [
            {
                "video_id": "video-a",
                "channel_id": "channel-1",
                "title": "Artificial intelligence breakthrough",
                "privacy_status": "public",
                "published_at": (
                    now - timedelta(hours=10)
                ).isoformat(),
                "views": 20,
                "likes": 2,
                "comments": 1,
            },
            {
                "video_id": "video-b",
                "channel_id": "channel-1",
                "title": "New technology discovery",
                "privacy_status": "public",
                "published_at": (
                    now - timedelta(hours=12)
                ).isoformat(),
                "views": 30,
                "likes": 3,
                "comments": 1,
            },
        ]

        videos_second = [
            {
                **videos_first[0],
                "views": 70,
                "likes": 7,
                "comments": 2,
            },
            {
                **videos_first[1],
                "views": 60,
                "likes": 6,
                "comments": 2,
            },
        ]

        async with session_factory() as session:
            await snapshot_service.create_snapshots(
                session,
                videos=videos_first,
                captured_at=(
                    now - timedelta(hours=1)
                ),
            )

            await snapshot_service.create_snapshots(
                session,
                videos=videos_second,
                captured_at=now,
            )

            evidence = await evidence_service.build(
                session,
                "channel-1",
            )

        assert evidence["snapshot_count"] == 4
        assert evidence["unique_video_count"] == 2
        assert evidence["source_video_count"] == 2
        assert evidence["video_count"] == 2

        print(
            "PASS: repeated snapshots collapse "
            "to one latest observation per video."
        )

        assert evidence["total_views"] == 130

        print(
            "PASS: audience evidence uses latest "
            "statistics rather than stale observations."
        )

        assert evidence["strategy_ready"] is True

        print(
            "PASS: latest public observations can "
            "produce strategy-ready evidence."
        )

        assert (
            evidence["sample_confidence"]
            == 0.1
        )

        print(
            "PASS: repeated polling cannot inflate "
            "sample confidence."
        )

        analyzed_ids = {
            video["video_id"]
            for video in evidence["videos"]
        }

        assert analyzed_ids == {
            "video-a",
            "video-b",
        }

        print(
            "PASS: analyzer receives each video "
            "exactly once."
        )

        try:
            async with session_factory() as session:
                await evidence_service.build(
                    session,
                    "",
                )
        except ValueError:
            pass
        else:
            raise AssertionError(
                "Empty channel ID must fail."
            )

        print(
            "PASS: empty channel IDs are rejected."
        )

        await engine.dispose()

    print("=" * 72)
    print(
        "ALL YOUTUBE PERFORMANCE EVIDENCE "
        "SERVICE TESTS PASSED"
    )
    print("=" * 72)


asyncio.run(main())
