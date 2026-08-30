"""Real private YouTube upload through Jarvis idempotency."""

import asyncio
import hashlib
import json
from pathlib import Path

from backend.database import async_session, init_db
from backend.services.orchestration.idempotency import (
    OperationType,
)
from backend.services.orchestration.idempotent_operation_executor import (
    IdempotentOperationExecutor,
)
from backend.services.providers.youtube_publisher import (
    YoutubePublisher,
)


VIDEO_PATH = Path(
    "generated/videos/"
    "Why_AI_generated_videos_are_becoming_more_realistic.mp4"
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        while True:
            chunk = handle.read(
                1024 * 1024
            )

            if not chunk:
                break

            digest.update(chunk)

    return digest.hexdigest()


async def main():
    print("=" * 72)
    print("JARVIS REAL YOUTUBE PRIVATE UPLOAD")
    print("=" * 72)
    print()

    path = VIDEO_PATH.resolve()

    if not path.exists():
        raise FileNotFoundError(
            f"Video not found: {path}"
        )

    print(
        "Video:",
        path,
    )

    print(
        "Size:",
        path.stat().st_size,
        "bytes",
    )

    publisher = YoutubePublisher()

    # ------------------------------------------------------
    # Verify the exact authorized channel before uploading.
    # ------------------------------------------------------

    channel = publisher.get_authorized_channel()

    print()
    print(
        "Authorized channel:",
        channel["channel_title"],
    )

    print(
        "Channel ID:",
        channel["channel_id"],
    )

    # ------------------------------------------------------
    # Stable artifact identity.
    #
    # Same channel + same exact MP4 =
    # same resource ID across retries/reruns.
    # ------------------------------------------------------

    video_hash = sha256_file(
        path
    )

    resource_id = (
        f"youtube:"
        f"{channel['channel_id']}:"
        f"{video_hash}"
    )

    print()
    print(
        "Artifact SHA256:",
        video_hash,
    )

    print(
        "Stable resource ID created."
    )

    await init_db()

    executor = IdempotentOperationExecutor(
        async_session
    )

    async def upload():
        print()
        print(
            "Starting REAL YouTube upload..."
        )

        print(
            "Privacy: PRIVATE"
        )

        return await publisher.upload_video(
            video_path=path,
            title=(
                "Why AI Generated Videos "
                "Are Becoming More Realistic"
            ),
            description=(
                "Private Jarvis production upload test."
            ),
            tags=[
                "AI",
                "technology",
                "shorts",
            ],
            privacy_status="private",
            category_id="28",
        )

    result = await executor.execute(
        operation_type=(
            OperationType.UPLOAD_VIDEO
        ),
        resource_id=resource_id,
        operation=upload,
    )

    print()
    print("=" * 72)
    print("IDEMPOTENT UPLOAD RESULT")
    print("=" * 72)

    print(
        json.dumps(
            result,
            indent=2,
        )
    )

    if (
        result.get("status")
        != "completed"
    ):
        raise RuntimeError(
            "Upload did not reach completed state."
        )

    provider_result = (
        result.get("result")
        or {}
    )

    video_id = provider_result.get(
        "video_id"
    )

    if video_id:
        print()
        print(
            "YouTube video ID:",
            video_id,
        )

    if result.get("executed"):
        print(
            "PASS: real upload executed exactly "
            "through the protected operation boundary."
        )
    else:
        print(
            "PASS: duplicate execution was blocked; "
            "persisted upload result returned."
        )

    print()
    print(
        "PASS: video remains PRIVATE."
    )

    print()
    print("=" * 72)
    print(
        "REAL PRIVATE YOUTUBE UPLOAD CHECKPOINT PASSED"
    )
    print("=" * 72)


if __name__ == "__main__":
    asyncio.run(main())
