"""Tests for YouTube video statistics retrieval."""

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock

from backend.services.providers.youtube_publisher import (
    YoutubePublisher,
    YoutubePublisherConfig,
)


def main():
    print("=" * 72)
    print("YOUTUBE VIDEO STATISTICS TEST")
    print("=" * 72)

    with TemporaryDirectory() as directory:
        root = Path(directory)

        publisher = YoutubePublisher(
            YoutubePublisherConfig(
                client_secret_path=(
                    root / "client.json"
                ),
                token_path=(
                    root / "token.json"
                ),
            )
        )

        fake_client = MagicMock()

        fake_response = {
            "items": [
                {
                    "id": "video-001",
                    "snippet": {
                        "channelId": "channel-123",
                        "title": "First Jarvis Short",
                        "publishedAt": (
                            "2026-08-30T12:00:00Z"
                        ),
                    },
                    "statistics": {
                        "viewCount": "12500",
                        "likeCount": "840",
                        "commentCount": "73",
                    },
                    "status": {
                        "privacyStatus": "public",
                    },
                },
                {
                    "id": "video-002",
                    "snippet": {
                        "channelId": "channel-123",
                        "title": "Second Jarvis Short",
                        "publishedAt": (
                            "2026-08-30T14:00:00Z"
                        ),
                    },
                    "statistics": {
                        "viewCount": "500",
                    },
                    "status": {
                        "privacyStatus": "private",
                    },
                },
            ],
        }

        (
            fake_client
            .videos
            .return_value
            .list
            .return_value
            .execute
            .return_value
        ) = fake_response

        publisher._build_client = (
            lambda: fake_client
        )

        result = publisher.get_video_statistics(
            [
                "video-001",
                "video-002",
                "video-001",
                "   ",
            ]
        )

        assert len(result) == 2

        first = result[0]

        assert first == {
            "video_id": "video-001",
            "channel_id": "channel-123",
            "title": "First Jarvis Short",
            "published_at": (
                "2026-08-30T12:00:00Z"
            ),
            "privacy_status": "public",
            "views": 12500,
            "likes": 840,
            "comments": 73,
        }

        second = result[1]

        assert (
            second["video_id"]
            == "video-002"
        )

        assert second["views"] == 500
        assert second["likes"] == 0
        assert second["comments"] == 0

        call = (
            fake_client
            .videos
            .return_value
            .list
            .call_args
        )

        assert call.kwargs["part"] == (
            "id,snippet,statistics,status"
        )

        assert call.kwargs["id"] == (
            "video-001,video-002"
        )

        print(
            "PASS: video statistics are "
            "retrieved and normalized."
        )

        print(
            "PASS: missing engagement counts "
            "safely become zero."
        )

        print(
            "PASS: duplicate and empty video "
            "IDs are removed."
        )

        # ---------------------------------------------
        # Invalid provider counts must fail closed to 0
        # ---------------------------------------------

        (
            fake_client
            .videos
            .return_value
            .list
            .return_value
            .execute
            .return_value
        ) = {
            "items": [
                {
                    "id": "video-bad",
                    "snippet": {},
                    "statistics": {
                        "viewCount": "invalid",
                        "likeCount": None,
                        "commentCount": -4,
                    },
                    "status": {},
                },
            ],
        }

        bad = publisher.get_video_statistics(
            ["video-bad"]
        )

        assert bad[0]["views"] == 0
        assert bad[0]["likes"] == 0
        assert bad[0]["comments"] == 0

        print(
            "PASS: malformed provider counts "
            "are normalized safely."
        )

        # ---------------------------------------------
        # Empty input must not call YouTube
        # ---------------------------------------------

        before = (
            fake_client
            .videos
            .return_value
            .list
            .call_count
        )

        empty = publisher.get_video_statistics(
            []
        )

        after = (
            fake_client
            .videos
            .return_value
            .list
            .call_count
        )

        assert empty == []
        assert before == after

        print(
            "PASS: empty input performs "
            "no provider request."
        )

    print("=" * 72)
    print(
        "ALL YOUTUBE VIDEO STATISTICS "
        "TESTS PASSED"
    )
    print("=" * 72)


if __name__ == "__main__":
    main()
