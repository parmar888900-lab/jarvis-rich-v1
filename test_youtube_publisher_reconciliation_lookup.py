"""YouTube publisher reconciliation lookup regression."""

from unittest.mock import MagicMock

from backend.services.providers.youtube_publisher import (
    YoutubePublisher,
)


def main():

    print("=" * 72)
    print(
        "YOUTUBE PROVIDER MARKER LOOKUP TEST"
    )
    print("=" * 72)

    publisher = YoutubePublisher()

    client = MagicMock()

    # Authorized channel + uploads playlist.
    (
        client.channels()
        .list()
        .execute.return_value
    ) = {
        "items": [
            {
                "id": "channel-123",
                "contentDetails": {
                    "relatedPlaylists": {
                        "uploads": (
                            "uploads-playlist-123"
                        ),
                    },
                },
            },
        ],
    }

    # Recent uploaded video IDs.
    (
        client.playlistItems()
        .list()
        .execute.return_value
    ) = {
        "items": [
            {
                "contentDetails": {
                    "videoId": "video-old",
                },
            },
            {
                "contentDetails": {
                    "videoId": "video-match",
                },
            },
        ],
    }

    # Full snippets contain tags.
    (
        client.videos()
        .list()
        .execute.return_value
    ) = {
        "items": [
            {
                "id": "video-old",
                "snippet": {
                    "title": "Old Video",
                    "tags": [
                        "ordinary-tag",
                    ],
                },
            },
            {
                "id": "video-match",
                "snippet": {
                    "title": (
                        "Recovered Jarvis Upload"
                    ),
                    "tags": [
                        "shorts",
                        "jarvis-op-test-marker",
                    ],
                },
            },
        ],
    }

    publisher._build_client = (
        lambda: client
    )

    found = (
        publisher
        .find_uploaded_video_by_operation_tag(
            "jarvis-op-test-marker",
            max_items=50,
        )
    )

    assert found == {
        "channel_id": "channel-123",
        "video_id": "video-match",
        "title": (
            "Recovered Jarvis Upload"
        ),
        "operation_tag": (
            "jarvis-op-test-marker"
        ),
    }

    print(
        "PASS: uploads playlist is read."
    )

    print(
        "PASS: snippet tags identify the "
        "exact Jarvis operation."
    )

    # --------------------------------------------------
    # No matching tag returns None, not safe-to-retry.
    # The reconciler decides the latter.
    # --------------------------------------------------

    (
        client.videos()
        .list()
        .execute.return_value
    ) = {
        "items": [
            {
                "id": "video-old",
                "snippet": {
                    "title": "Old Video",
                    "tags": [
                        "different-marker",
                    ],
                },
            },
        ],
    }

    missing = (
        publisher
        .find_uploaded_video_by_operation_tag(
            "jarvis-op-missing",
            max_items=50,
        )
    )

    assert missing is None

    print(
        "PASS: missing provider marker "
        "returns no false completion."
    )

    print("=" * 72)


if __name__ == "__main__":
    main()
