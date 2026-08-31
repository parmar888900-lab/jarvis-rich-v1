"""YouTube agent upload command-routing regression test."""

import asyncio
import tempfile
from pathlib import Path

from backend.services.agent_handlers.youtube import (
    YoutubeAgentHandler,
)
from backend.services.commander import Commander
from backend.services.orchestration.idempotency import (
    OperationType,
)


class FakePublisher:
    def __init__(self):
        self.upload_calls = []

    def get_authorized_channel(self):
        return {
            "status": "authorized",
            "channel_id": "test-channel-123",
            "channel_title": "Test Channel",
        }

    async def upload_video(
        self,
        *,
        video_path,
        title,
        description="",
        tags=None,
        privacy_status="private",
        category_id="22",
        operation_tag=None,
    ):
        self.upload_calls.append(
            {
                "video_path": str(video_path),
                "title": title,
                "description": description,
                "tags": tags,
                "privacy_status": privacy_status,
                "category_id": category_id,
                "operation_tag": operation_tag,
            }
        )

        return {
            "status": "uploaded",
            "video_id": "fake-video-123",
            "privacy_status": privacy_status,
            "title": title,
        }


class FakeExecutor:
    def __init__(self):
        self.calls = []

    async def execute(
        self,
        *,
        operation_type,
        resource_id,
        operation,
    ):
        self.calls.append(
            {
                "operation_type": operation_type,
                "resource_id": resource_id,
            }
        )

        result = await operation()

        return {
            "status": "completed",
            "executed": True,
            "idempotency_key": "fake-key",
            "result": result,
        }


class FakeRegistry:
    def __init__(self, handler):
        self.handler = handler

    def get(self, agent):
        if agent != "youtube":
            raise KeyError(agent)

        return self.handler


async def main():
    print("=" * 72)
    print("YOUTUBE AGENT COMMAND ROUTING TEST")
    print("=" * 72)

    with tempfile.TemporaryDirectory() as temp_dir:
        video = (
            Path(temp_dir)
            / "test-video.mp4"
        )

        video.write_bytes(
            b"jarvis-youtube-test-video"
        )

        handler = YoutubeAgentHandler.__new__(
            YoutubeAgentHandler
        )

        publisher = FakePublisher()
        executor = FakeExecutor()

        handler.publisher = publisher
        handler.operation_executor = executor

        commander = Commander.__new__(
            Commander
        )

        commander.registry = FakeRegistry(
            handler
        )

        result = await commander.route(
            agent="youtube",
            task="upload_video",
            command_id="command-test-001",
            parameters={
                "video_path": str(video),
                "title": "Jarvis Test Video",
                "description": (
                    "Command routing test."
                ),
                "tags": [
                    "jarvis",
                    "test",
                ],
                "privacy_status": "private",
                "category_id": "28",
            },
        )

        assert result["status"] == "completed"
        assert result["task"] == "upload_video"
        assert (
            result["command_id"]
            == "command-test-001"
        )

        assert len(
            publisher.upload_calls
        ) == 1

        upload = publisher.upload_calls[0]

        assert (
            upload["privacy_status"]
            == "private"
        )

        assert (
            upload["title"]
            == "Jarvis Test Video"
        )

        assert (
            isinstance(
                upload["operation_tag"],
                str,
            )
        )

        assert (
            upload[
                "operation_tag"
            ].startswith(
                "jarvis-op-"
            )
        )

        assert len(
            executor.calls
        ) == 1

        operation_call = executor.calls[0]

        assert (
            operation_call["operation_type"]
            == OperationType.UPLOAD_VIDEO
        )

        assert operation_call[
            "resource_id"
        ].startswith(
            "youtube:test-channel-123:"
        )

        print(
            "PASS: Commander expanded parameters "
            "into YouTube agent."
        )

        print(
            "PASS: YouTube agent generated stable "
            "artifact identity."
        )

        print(
            "PASS: upload passed through "
            "IdempotentOperationExecutor."
        )

        print(
            "PASS: PRIVATE visibility reached "
            "publisher."
        )

        # --------------------------------------------------
        # Public publishing must fail closed by default.
        # --------------------------------------------------

        try:
            await commander.route(
                agent="youtube",
                task="upload_video",
                command_id=(
                    "command-test-public"
                ),
                parameters={
                    "video_path": str(video),
                    "title": (
                        "Public Safety Test"
                    ),
                    "privacy_status": (
                        "public"
                    ),
                },
            )

        except ValueError as exc:
            assert (
                "Public YouTube publishing "
                "is locked"
                in str(exc)
            )

            print(
                "PASS: PUBLIC publishing "
                "fails closed by default."
            )

        else:
            raise AssertionError(
                "Public upload should have "
                "been blocked."
            )

        # Public safety test must not have reached
        # the fake publisher.
        assert len(
            publisher.upload_calls
        ) == 1

    print()
    print("=" * 72)
    print(
        "YOUTUBE AGENT COMMAND ROUTING PASSED"
    )
    print("=" * 72)


if __name__ == "__main__":
    asyncio.run(main())
