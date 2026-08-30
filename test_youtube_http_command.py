"""FastAPI /command -> YouTube upload routing regression test.

This test performs NO real YouTube upload.
"""

import json
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app import app
from backend.routes import commander as commander_route
from backend.services.agent_handlers.youtube import (
    YoutubeAgentHandler,
)
from backend.services.orchestration.idempotency import (
    OperationType,
)


class FakePublisher:
    def __init__(self):
        self.upload_calls = []

    def get_authorized_channel(self):
        return {
            "status": "authorized",
            "channel_id": "http-test-channel",
            "channel_title": "HTTP Test Channel",
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
    ):
        self.upload_calls.append(
            {
                "video_path": str(video_path),
                "title": title,
                "description": description,
                "tags": tags,
                "privacy_status": privacy_status,
                "category_id": category_id,
            }
        )

        return {
            "status": "uploaded",
            "video_id": "fake-http-video-123",
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

        provider_result = await operation()

        return {
            "status": "completed",
            "executed": True,
            "idempotency_key": (
                "fake-http-idempotency-key"
            ),
            "result": provider_result,
        }


def get_youtube_handler():
    return (
        commander_route
        .commander
        .registry
        .get("youtube")
    )


def main():
    print("=" * 72)
    print("FASTAPI YOUTUBE COMMAND BOUNDARY TEST")
    print("=" * 72)
    print()

    handler = get_youtube_handler()

    if not isinstance(
        handler,
        YoutubeAgentHandler,
    ):
        raise AssertionError(
            "Registered youtube handler has "
            "unexpected type."
        )

    original_publisher = handler.publisher
    original_executor = (
        handler.operation_executor
    )

    fake_publisher = FakePublisher()
    fake_executor = FakeExecutor()

    handler.publisher = fake_publisher
    handler.operation_executor = (
        fake_executor
    )

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            video = (
                Path(temp_dir)
                / "http-test-video.mp4"
            )

            video.write_bytes(
                b"jarvis-http-youtube-test"
            )

            # --------------------------------------------------
            # Use the REAL FastAPI application and REAL
            # /command endpoint.
            #
            # The publisher/executor are fake, so no external
            # YouTube side effect can occur.
            # --------------------------------------------------

            with TestClient(app) as client:
                response = client.post(
                    "/command",
                    json={
                        "agent": "youtube",
                        "task": "upload_video",
                        "parameters": {
                            "video_path": str(
                                video
                            ),
                            "title": (
                                "HTTP Jarvis Test"
                            ),
                            "description": (
                                "FastAPI routing test."
                            ),
                            "tags": [
                                "jarvis",
                                "http-test",
                            ],
                            "privacy_status": (
                                "private"
                            ),
                            "category_id": "28",
                        },
                    },
                )

                print(
                    "POST /command status:",
                    response.status_code,
                )

                print(
                    "POST /command response:",
                    json.dumps(
                        response.json(),
                        indent=2,
                    ),
                )

                assert (
                    response.status_code
                    == 200
                )

                submit_result = (
                    response.json()
                )

                command_id = (
                    submit_result[
                        "command_id"
                    ]
                )

                assert command_id

                # ----------------------------------------------
                # Verify the command record through the REAL
                # GET endpoint.
                # ----------------------------------------------

                status_response = client.get(
                    f"/command/{command_id}"
                )

                print()
                print(
                    "GET /command status:",
                    status_response.status_code,
                )

                print(
                    "Stored command:",
                    json.dumps(
                        status_response.json(),
                        indent=2,
                    ),
                )

                assert (
                    status_response.status_code
                    == 200
                )

                command = (
                    status_response.json()
                )

                assert (
                    str(
                        command["status"]
                    ).lower()
                    == "completed"
                )

                stored_result = json.loads(
                    command["result"]
                )

                assert (
                    stored_result["task"]
                    == "upload_video"
                )

                assert (
                    stored_result[
                        "privacy_status"
                    ]
                    == "private"
                )

                assert (
                    stored_result[
                        "upload"
                    ]["result"]["video_id"]
                    == "fake-http-video-123"
                )

                assert (
                    stored_result[
                        "upload"
                    ]["executed"]
                    is True
                )

                assert len(
                    fake_publisher.upload_calls
                ) == 1

                assert len(
                    fake_executor.calls
                ) == 1

                assert (
                    fake_executor.calls[0][
                        "operation_type"
                    ]
                    == OperationType.UPLOAD_VIDEO
                )

                assert (
                    fake_executor.calls[0][
                        "resource_id"
                    ].startswith(
                        "youtube:"
                        "http-test-channel:"
                    )
                )

                print()
                print(
                    "PASS: POST /command accepted "
                    "YouTube upload parameters."
                )

                print(
                    "PASS: HTTP -> Commander -> "
                    "YouTube agent routing works."
                )

                print(
                    "PASS: protected upload boundary "
                    "was invoked."
                )

                print(
                    "PASS: command result was "
                    "persisted."
                )

                print(
                    "PASS: publisher remained PRIVATE."
                )

                # ----------------------------------------------
                # Public request must fail closed.
                # ----------------------------------------------

                calls_before_public = len(
                    fake_publisher.upload_calls
                )

                public_response = client.post(
                    "/command",
                    json={
                        "agent": "youtube",
                        "task": "upload_video",
                        "parameters": {
                            "video_path": str(
                                video
                            ),
                            "title": (
                                "HTTP Public Safety Test"
                            ),
                            "privacy_status": (
                                "public"
                            ),
                        },
                    },
                )

                print()
                print(
                    "Public request status:",
                    public_response.status_code,
                )

                assert (
                    public_response.status_code
                    == 500
                )

                assert len(
                    fake_publisher.upload_calls
                ) == calls_before_public

                print(
                    "PASS: PUBLIC request failed "
                    "before provider execution."
                )

    finally:
        handler.publisher = (
            original_publisher
        )

        handler.operation_executor = (
            original_executor
        )

    print()
    print("=" * 72)
    print(
        "FASTAPI YOUTUBE COMMAND BOUNDARY PASSED"
    )
    print("=" * 72)


if __name__ == "__main__":
    main()
