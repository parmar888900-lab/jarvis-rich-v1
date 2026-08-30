"""Tests for authenticated YouTube publishing provider."""

import asyncio
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

from backend.services.providers.youtube_publisher import (
    YoutubeAuthorizationRequired,
    YoutubePublisher,
    YoutubePublisherConfig,
)


async def main():
    print("=" * 70)
    print("YOUTUBE PUBLISHER FOUNDATION TEST")
    print()

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)

        video = root / "short.mp4"
        video.write_bytes(
            b"fake-video-data"
        )

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

        # -------------------------------------------------
        # Missing authorization must fail safely
        # -------------------------------------------------

        try:
            publisher._load_credentials()
        except YoutubeAuthorizationRequired:
            pass
        else:
            raise AssertionError(
                "Missing OAuth token did not fail safely."
            )

        print(
            "PASS: missing OAuth authorization "
            "fails safely."
        )

        # -------------------------------------------------
        # Invalid privacy must fail before API execution
        # -------------------------------------------------

        try:
            publisher._upload_sync(
                video_path=video,
                title="Test",
                description="",
                tags=None,
                privacy_status="secret",
                category_id="22",
            )
        except ValueError:
            pass
        else:
            raise AssertionError(
                "Invalid privacy setting was accepted."
            )

        print(
            "PASS: invalid privacy state is rejected."
        )

        # -------------------------------------------------
        # Simulated API upload
        # -------------------------------------------------

        fake_client = MagicMock()
        fake_request = MagicMock()

        fake_request.next_chunk.side_effect = [
            (None, None),
            (
                None,
                {
                    "id": "youtube-test-123",
                },
            ),
        ]

        fake_client.videos.return_value.insert.return_value = (
            fake_request
        )

        publisher._build_client = lambda: fake_client

        result = await publisher.upload_video(
            video_path=video,
            title="Jarvis Test Short",
            description="Test description",
            tags=[
                "jarvis",
                "shorts",
            ],
        )

        assert result == {
            "status": "uploaded",
            "video_id": "youtube-test-123",
            "privacy_status": "private",
            "title": "Jarvis Test Short",
        }

        assert (
            fake_client
            .videos
            .return_value
            .insert
            .call_count
            == 1
        )

        call = (
            fake_client
            .videos
            .return_value
            .insert
            .call_args
        )

        body = call.kwargs["body"]

        assert (
            body["status"]["privacyStatus"]
            == "private"
        )

        assert (
            body["snippet"]["title"]
            == "Jarvis Test Short"
        )

        print(
            "PASS: simulated resumable upload "
            "returns provider video ID."
        )

        print(
            "PASS: uploads default to PRIVATE."
        )

    print()
    print("=" * 70)
    print(
        "ALL YOUTUBE PUBLISHER FOUNDATION "
        "TESTS PASSED"
    )


if __name__ == "__main__":
    asyncio.run(main())
