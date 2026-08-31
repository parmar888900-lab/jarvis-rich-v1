"""YouTube malformed-success uncertainty regression."""

import asyncio
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

from backend.services.providers.youtube_publisher import (
    YoutubePublisher,
    YoutubeUploadUncertainError,
)


async def main():

    print("=" * 72)
    print(
        "YOUTUBE UNCERTAIN RESPONSE TEST"
    )
    print("=" * 72)

    with tempfile.TemporaryDirectory() as directory:

        video = (
            Path(directory)
            / "test-video.mp4"
        )

        video.write_bytes(
            b"jarvis-uncertain-response-test"
        )

        publisher = YoutubePublisher()

        client = MagicMock()
        request = MagicMock()

        # Simulate YouTube's resumable call returning
        # a nominal response but without the video ID.
        request.next_chunk.return_value = (
            None,
            {},
        )

        (
            client.videos()
            .insert.return_value
        ) = request

        publisher._build_client = (
            lambda: client
        )

        try:
            await publisher.upload_video(
                video_path=video,
                title=(
                    "Uncertain YouTube Response"
                ),
                privacy_status="private",
                operation_tag=(
                    "jarvis-op-test-uncertain"
                ),
            )

        except YoutubeUploadUncertainError as exc:

            assert (
                "video ID"
                in str(exc)
            )

        else:
            raise AssertionError(
                "Missing provider video ID "
                "must be classified as uncertain."
            )

    print(
        "PASS: completed transfer without "
        "video_id is externally uncertain."
    )

    print(
        "PASS: malformed provider success "
        "cannot become ordinary FAILED."
    )

    print("=" * 72)


if __name__ == "__main__":
    asyncio.run(main())
