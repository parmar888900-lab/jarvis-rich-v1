"""Regression tests for policy-owned YouTube publication."""

import asyncio

from backend.services.agent_handlers.youtube import (
    YoutubeAgentHandler,
)
from backend.services.orchestration.youtube_release_policy import (
    YoutubeReleasePolicy,
)


def build_cycle_result(
    *,
    score=85.0,
    video_id="video-123",
    cycle_status="completed",
    eligible=True,
    selected=True,
    upload_status="completed",
    privacy_status="private",
):
    return {
        "status": cycle_status,
        "selected_trend": {
            "production_selection": {
                "eligible": eligible,
                "selected": selected,
                "production_score": score,
            }
        },
        "upload": {
            "status": upload_status,
            "privacy_status": privacy_status,
            "upload": {
                "status": "completed",
                "executed": True,
                "result": {
                    "video_id": video_id,
                },
            },
        },
    }


class FakePublisher:
    def __init__(self):
        self.channel_calls = 0
        self.privacy_calls = []

    def get_authorized_channel(self):
        self.channel_calls += 1

        return {
            "channel_id": "channel-123",
            "channel_title": "Test Channel",
        }

    async def set_video_privacy(
        self,
        *,
        video_id: str,
        privacy_status: str,
    ) -> dict:
        self.privacy_calls.append(
            {
                "video_id": video_id,
                "privacy_status": privacy_status,
            }
        )

        return {
            "status": "updated",
            "video_id": video_id,
            "privacy_status": privacy_status,
        }


class FakeOperationExecutor:
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
            "idempotency_key": "test-publish-key",
            "result": provider_result,
        }


class ReplayExecutor:
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

        return {
            "status": "completed",
            "executed": False,
            "idempotency_key": "test-publish-key",
            "result": {
                "status": "updated",
                "video_id": "video-123",
                "privacy_status": "public",
            },
        }


async def main():
    cycle = build_cycle_result()

    # --------------------------------------------------------
    # Default policy fails closed
    # --------------------------------------------------------

    default_handler = YoutubeAgentHandler()

    default_publisher = FakePublisher()
    default_executor = FakeOperationExecutor()

    default_handler.publisher = default_publisher
    default_handler.operation_executor = default_executor

    assert "publish_video" in default_handler.supported_tasks

    result = await default_handler.execute(
        task="publish_video",
        command_id="default-policy",
        cycle_result=cycle,
        manual_approved=True,
    )

    assert result["status"] == "denied"
    assert (
        "release_disabled"
        in result["release_decision"]["reasons"]
    )

    assert default_publisher.channel_calls == 0
    assert default_publisher.privacy_calls == []
    assert default_executor.calls == []

    print(
        "PASS: default release policy fails closed "
        "before provider access."
    )

    # --------------------------------------------------------
    # Forged release decision is not accepted
    # --------------------------------------------------------

    try:
        await default_handler.execute(
            task="publish_video",
            command_id="forged-decision",
            cycle_result=cycle,
            manual_approved=True,
            release_decision={
                "authorized": True,
                "video_id": "attacker-video",
                "target_privacy_status": "public",
            },
        )

    except TypeError:
        pass

    else:
        raise AssertionError(
            "Caller-supplied release_decision "
            "must not be accepted."
        )

    assert default_publisher.channel_calls == 0
    assert default_publisher.privacy_calls == []
    assert default_executor.calls == []

    print(
        "PASS: caller cannot inject a forged "
        "release decision."
    )

    # --------------------------------------------------------
    # Enabled release policy
    # --------------------------------------------------------

    policy = YoutubeReleasePolicy(
        enabled=True,
        min_production_score=70.0,
        require_manual_approval=True,
    )

    handler = YoutubeAgentHandler(
        release_policy=policy,
    )

    publisher = FakePublisher()
    executor = FakeOperationExecutor()

    handler.publisher = publisher
    handler.operation_executor = executor

    # --------------------------------------------------------
    # Manual approval required
    # --------------------------------------------------------

    result = await handler.execute(
        task="publish_video",
        command_id="manual-required",
        cycle_result=cycle,
        manual_approved=False,
    )

    assert result["status"] == "denied"

    assert (
        "manual_approval_required"
        in result["release_decision"]["reasons"]
    )

    assert publisher.channel_calls == 0
    assert publisher.privacy_calls == []
    assert executor.calls == []

    print(
        "PASS: enabled policy still requires "
        "manual approval."
    )

    # --------------------------------------------------------
    # Low production score denied
    # --------------------------------------------------------

    weak_cycle = build_cycle_result(
        score=69.0,
    )

    result = await handler.execute(
        task="publish_video",
        command_id="weak-score",
        cycle_result=weak_cycle,
        manual_approved=True,
    )

    assert result["status"] == "denied"

    assert (
        "production_score_below_threshold"
        in result["release_decision"]["reasons"]
    )

    assert publisher.channel_calls == 0
    assert publisher.privacy_calls == []
    assert executor.calls == []

    print(
        "PASS: production score gate blocks "
        "weak evidence."
    )

    # --------------------------------------------------------
    # Failed cycle denied
    # --------------------------------------------------------

    failed_cycle = build_cycle_result(
        cycle_status="failed",
    )

    result = await handler.execute(
        task="publish_video",
        command_id="failed-cycle",
        cycle_result=failed_cycle,
        manual_approved=True,
    )

    assert result["status"] == "denied"

    assert (
        "production_cycle_not_completed"
        in result["release_decision"]["reasons"]
    )

    assert publisher.channel_calls == 0
    assert publisher.privacy_calls == []
    assert executor.calls == []

    print(
        "PASS: incomplete production cycle "
        "cannot publish."
    )

    # --------------------------------------------------------
    # Non-private upload denied
    # --------------------------------------------------------

    non_private = build_cycle_result(
        privacy_status="unlisted",
    )

    result = await handler.execute(
        task="publish_video",
        command_id="non-private",
        cycle_result=non_private,
        manual_approved=True,
    )

    assert result["status"] == "denied"

    assert (
        "video_not_private"
        in result["release_decision"]["reasons"]
    )

    assert publisher.channel_calls == 0
    assert publisher.privacy_calls == []
    assert executor.calls == []

    print(
        "PASS: release requires completed "
        "PRIVATE upload."
    )

    # --------------------------------------------------------
    # Authorized publication
    # --------------------------------------------------------

    result = await handler.execute(
        task="publish_video",
        command_id="authorized-release",
        cycle_result=cycle,
        manual_approved=True,
    )

    assert result["status"] == "completed"
    assert result["video_id"] == "video-123"
    assert result["channel_id"] == "channel-123"
    assert result["privacy_status"] == "public"

    decision = result["release_decision"]

    assert decision["authorized"] is True
    assert decision["status"] == "authorized"
    assert decision["video_id"] == "video-123"
    assert (
        decision["target_privacy_status"]
        == "public"
    )

    print(
        "PASS: valid cycle evidence plus "
        "manual approval authorizes publication."
    )

    # --------------------------------------------------------
    # Video identity comes from cycle evidence
    # --------------------------------------------------------

    assert publisher.privacy_calls == [
        {
            "video_id": "video-123",
            "privacy_status": "public",
        }
    ]

    print(
        "PASS: video identity came from "
        "protected upload evidence."
    )

    # --------------------------------------------------------
    # Channel identity comes from OAuth provider
    # --------------------------------------------------------

    assert publisher.channel_calls == 1
    assert result["channel_id"] == "channel-123"

    print(
        "PASS: channel identity came from "
        "authenticated provider state."
    )

    # --------------------------------------------------------
    # PUBLISH_VIDEO operation identity
    # --------------------------------------------------------

    assert len(executor.calls) == 1

    call = executor.calls[0]

    assert (
        call["operation_type"].value
        == "publish_video"
    )

    assert (
        call["resource_id"]
        == "youtube-publish:channel-123:video-123"
    )

    print(
        "PASS: correct PUBLISH_VIDEO "
        "idempotency boundary used."
    )

    # --------------------------------------------------------
    # Idempotent replay
    # --------------------------------------------------------

    replay_executor = ReplayExecutor()

    handler.operation_executor = replay_executor

    privacy_calls_before = len(
        publisher.privacy_calls
    )

    replay = await handler.execute(
        task="publish_video",
        command_id="authorized-replay",
        cycle_result=cycle,
        manual_approved=True,
    )

    assert replay["status"] == "completed"
    assert replay["publish"]["executed"] is False

    assert (
        len(publisher.privacy_calls)
        == privacy_calls_before
    )

    assert (
        replay_executor.calls[0]["resource_id"]
        == "youtube-publish:channel-123:video-123"
    )

    print(
        "PASS: idempotent replay does not "
        "repeat provider publication."
    )

    print()
    print(
        "PASS: policy-owned YouTube publication "
        "regression suite complete."
    )


if __name__ == "__main__":
    asyncio.run(main())
