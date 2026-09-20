"""Real read-only YouTube analytics collection smoke test."""

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

from backend.models.youtube_performance_snapshot import (
    YoutubePerformanceSnapshotRecord,
)
from backend.services.analytics.youtube_performance_collector import (
    YoutubePerformanceCollector,
)
from backend.services.analytics.youtube_performance_snapshot_service import (
    YoutubePerformanceSnapshotService,
)
from backend.services.analytics.youtube_performance import (
    YoutubePerformanceAnalyzer,
)
from backend.services.providers.youtube_publisher import (
    YoutubePublisher,
)


async def main():
    print("=" * 72)
    print("REAL READ-ONLY YOUTUBE ANALYTICS SMOKE TEST")
    print("=" * 72)

    publisher = YoutubePublisher()

    print("")
    print("1. VERIFY AUTHORIZED CHANNEL")
    print("-" * 72)

    channel = await asyncio.to_thread(
        publisher.get_authorized_channel
    )

    channel_id = str(
        channel.get(
            "channel_id",
            "",
        )
    ).strip()

    channel_title = str(
        channel.get(
            "channel_title",
            "",
        )
    ).strip()

    if not channel_id:
        raise RuntimeError(
            "Authorized channel ID was empty."
        )

    print(
        "Authorized channel:",
        channel_title,
    )
    print(
        "Channel ID:",
        channel_id,
    )


    print("")
    print("2. DISCOVER RECENT UPLOADS")
    print("-" * 72)

    uploads = await asyncio.to_thread(
        publisher.get_recent_upload_video_ids,
        max_items=10,
    )

    if (
        uploads.get("channel_id")
        != channel_id
    ):
        raise RuntimeError(
            "Authorized-channel mismatch "
            "during upload discovery."
        )

    video_ids = uploads.get(
        "video_ids",
        [],
    )

    print(
        "Recent upload count:",
        len(video_ids),
    )

    for video_id in video_ids:
        print(
            " -",
            video_id,
        )


    print("")
    print("3. COLLECT + PERSIST TO TEMPORARY DATABASE")
    print("-" * 72)

    with tempfile.TemporaryDirectory() as directory:

        engine = create_async_engine(
            "sqlite+aiosqlite:///"
            f"{directory}/real_analytics.db"
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

        collector = YoutubePerformanceCollector(
            publisher=publisher,
            snapshot_service=(
                YoutubePerformanceSnapshotService()
            ),
        )

        captured_at = datetime.now(
            timezone.utc
        )

        async with session_factory() as session:

            result = await collector.collect(
                session,
                max_items=10,
                captured_at=captured_at,
            )

            print(
                "Collector status:",
                result["status"],
            )
            print(
                "Requested videos:",
                result[
                    "requested_video_count"
                ],
            )
            print(
                "Collected videos:",
                result[
                    "collected_video_count"
                ],
            )
            print(
                "Snapshots persisted:",
                result[
                    "snapshot_count"
                ],
            )

            history = (
                await collector
                .snapshot_service
                .list_latest_for_channel(
                    session,
                    channel_id,
                    limit=20,
                )
            )

            if (
                len(history)
                != result["snapshot_count"]
            ):
                raise RuntimeError(
                    "Persisted snapshot count "
                    "does not match collector result."
                )

            print("")
            print("4. SNAPSHOT DATA")
            print("-" * 72)

            provider_rows = []

            for snapshot in history:

                print("")
                print(
                    "Video:",
                    snapshot.video_id,
                )
                print(
                    "Title:",
                    snapshot.title,
                )
                print(
                    "Privacy:",
                    snapshot.privacy_status,
                )
                print(
                    "Views:",
                    snapshot.views,
                )
                print(
                    "Likes:",
                    snapshot.likes,
                )
                print(
                    "Comments:",
                    snapshot.comments,
                )
                print(
                    "Published:",
                    snapshot.published_at,
                )

                provider_rows.append(
                    {
                        "video_id": (
                            snapshot.video_id
                        ),
                        "channel_id": (
                            snapshot.channel_id
                        ),
                        "title": (
                            snapshot.title
                        ),
                        "published_at": (
                            snapshot.published_at
                            .replace(
                                tzinfo=timezone.utc
                            )
                            .isoformat()
                            if snapshot.published_at
                            is not None
                            else None
                        ),
                        "privacy_status": (
                            snapshot.privacy_status
                        ),
                        "views": snapshot.views,
                        "likes": snapshot.likes,
                        "comments": (
                            snapshot.comments
                        ),
                    }
                )


            print("")
            print("5. ANALYZE REAL PERFORMANCE")
            print("-" * 72)

            analyzer = (
                YoutubePerformanceAnalyzer()
            )

            analysis = analyzer.analyze(
                provider_rows,
                collected_at=captured_at,
            )

            print(
                "Source videos:",
                analysis["source_video_count"],
            )
            print(
                "Eligible public videos:",
                analysis["video_count"],
            )
            print(
                "Excluded videos:",
                analysis["excluded_video_count"],
            )
            print(
                "Total eligible views:",
                analysis["total_views"],
            )
            print(
                "Sample confidence:",
                analysis["sample_confidence"],
            )
            print(
                "Audience confidence:",
                analysis["audience_confidence"],
            )
            print(
                "Combined confidence:",
                analysis["confidence"],
            )
            print(
                "Strategy ready:",
                analysis["strategy_ready"],
            )
            print(
                "Baseline views/hour:",
                analysis[
                    "baseline_views_per_hour"
                ],
            )
            print(
                "Baseline engagement:",
                analysis[
                    "baseline_engagement_rate"
                ],
            )

            if analysis["videos"]:
                print("")
                print("PERFORMANCE RANKING")
                print("-" * 72)

                for index, video in enumerate(
                    analysis["videos"],
                    start=1,
                ):
                    print(
                        f"{index}.",
                        video["title"],
                    )
                    print(
                        "   score:",
                        video[
                            "performance_score"
                        ],
                    )
                    print(
                        "   views/hour:",
                        video[
                            "views_per_hour"
                        ],
                    )
                    print(
                        "   engagement:",
                        video[
                            "engagement_rate"
                        ],
                    )

        await engine.dispose()


    print("")
    print("=" * 72)
    print("REAL READ-ONLY ANALYTICS PIPELINE PASSED")
    print("=" * 72)
    print("")
    print(
        "No YouTube content was modified."
    )
    print(
        "No production database data was written."
    )


if __name__ == "__main__":
    asyncio.run(
        main()
    )
