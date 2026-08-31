"""Regression tests for YouTube privacy transitions."""

import asyncio

from backend.services.providers.youtube_publisher import (
    YoutubePublisher,
    YoutubeUploadUncertainError,
)


class FakeRequest:
    def __init__(
        self,
        response=None,
        error=None,
    ):
        self.response = response
        self.error = error

    def execute(self):
        if self.error is not None:
            raise self.error

        return self.response


class FakeVideos:
    def __init__(self):
        self.update_calls = []
        self.update_response = None
        self.update_error = None

    def update(
        self,
        *,
        part,
        body,
    ):
        self.update_calls.append(
            {
                "part": part,
                "body": body,
            }
        )

        return FakeRequest(
            response=self.update_response,
            error=self.update_error,
        )


class FakeClient:
    def __init__(self):
        self.video_api = FakeVideos()

    def videos(self):
        return self.video_api


def make_publisher(
    *,
    current_privacy="private",
):
    publisher = YoutubePublisher()
    client = FakeClient()

    publisher.get_authorized_channel = lambda: {
        "channel_id": "channel-1",
        "channel_title": "Test Channel",
    }

    publisher.get_video_status = lambda video_id: {
        "status": "found",
        "video_id": video_id,
        "channel_id": "channel-1",
        "authorized_channel_id": "channel-1",
        "privacy_status": current_privacy,
    }

    publisher._build_client = lambda: client

    return publisher, client


async def main():
    publisher, client = make_publisher()

    client.video_api.update_response = {
        "id": "video-1",
        "status": {
            "privacyStatus": "public",
        },
    }

    result = await publisher.set_video_privacy(
        video_id="video-1",
        privacy_status="public",
    )

    assert result["status"] == "updated"
    assert result["privacy_status"] == "public"
    assert result["already_in_state"] is False
    assert len(client.video_api.update_calls) == 1
    assert (
        client.video_api.update_calls[0]
        ["body"]["status"]["privacyStatus"]
        == "public"
    )

    print(
        "PASS: publisher performs explicit "
        "private-to-public update."
    )

    publisher, client = make_publisher(
        current_privacy="public"
    )

    result = await publisher.set_video_privacy(
        video_id="video-1",
        privacy_status="public",
    )

    assert result["already_in_state"] is True
    assert not client.video_api.update_calls

    print(
        "PASS: already-public video does not "
        "issue another provider update."
    )

    publisher, client = make_publisher()

    client.video_api.update_error = RuntimeError(
        "transport lost"
    )

    try:
        await publisher.set_video_privacy(
            video_id="video-1",
            privacy_status="public",
        )
    except YoutubeUploadUncertainError:
        pass
    else:
        raise AssertionError(
            "Ambiguous provider failure must be uncertain."
        )

    print(
        "PASS: provider transport failure is "
        "classified as uncertain."
    )

    publisher, client = make_publisher()

    client.video_api.update_response = {
        "id": "video-1",
        "status": {},
    }

    try:
        await publisher.set_video_privacy(
            video_id="video-1",
            privacy_status="public",
        )
    except YoutubeUploadUncertainError:
        pass
    else:
        raise AssertionError(
            "Malformed update response must be uncertain."
        )

    print(
        "PASS: malformed provider response "
        "fails closed as uncertain."
    )

    publisher, _ = make_publisher()

    publisher.get_video_status = lambda video_id: {
        "status": "found",
        "video_id": video_id,
        "channel_id": "wrong-channel",
        "authorized_channel_id": "channel-1",
        "privacy_status": "private",
    }

    try:
        await publisher.set_video_privacy(
            video_id="video-1",
            privacy_status="public",
        )
    except Exception as exc:
        assert (
            "does not belong"
            in str(exc)
        )
    else:
        raise AssertionError(
            "Cross-channel publication must fail."
        )

    print(
        "PASS: publisher refuses cross-channel "
        "privacy mutation."
    )

    print(
        "PASS: YouTube publisher privacy "
        "regression suite complete."
    )


if __name__ == "__main__":
    asyncio.run(main())
