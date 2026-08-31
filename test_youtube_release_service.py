"""Regression tests for the protected internal YouTube release service."""

import asyncio

from backend.services.orchestration.youtube_release_policy import (
    YoutubeReleasePolicy,
)
from backend.services.orchestration.youtube_release_service import (
    YoutubeReleaseService,
)


def build_evidence(
    *,
    score=88.0,
    video_id="video-123",
    privacy_status="private",
):
    return {
        "cycle_id": "cycle-123",
        "status": "completed",
        "selected_trend": {
            "production_selection": {
                "eligible": True,
                "selected": True,
                "production_score": score,
            },
        },
        "upload": {
            "status": "completed",
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


class FakeSession:
    pass


class FakeSessionContext:
    async def __aenter__(self):
        return FakeSession()

    async def __aexit__(
        self,
        exc_type,
        exc,
        traceback,
    ):
        return False


def fake_session_factory():
    return FakeSessionContext()


class FakeEvidenceService:
    def __init__(self, evidence):
        self.evidence = evidence
        self.calls = []

    async def resolve(
        self,
        session,
        *,
        cycle_id,
    ):
        self.calls.append(
            {
                "session": session,
                "cycle_id": cycle_id,
            }
        )

        return self.evidence


class FakePublisher:
    def __init__(self):
        self.channel_calls = 0
        self.privacy_calls = []

    def get_authorized_channel(self):
        self.channel_calls += 1

        return {
            "channel_id": "channel-123",
        }

    async def set_video_privacy(
        self,
        *,
        video_id,
        privacy_status,
    ):
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

        # Simulate an already-completed persistent operation.
        # The provider operation must not execute.
        return {
            "status": "completed",
            "executed": False,
            "result": {
                "status": "updated",
                "video_id": "video-123",
                "privacy_status": "public",
            },
        }


async def main():
    # ========================================================
    # Default policy: fail closed before provider access
    # ========================================================

    evidence_service = FakeEvidenceService(
        build_evidence()
    )

    publisher = FakePublisher()
    executor = FakeExecutor()

    service = YoutubeReleaseService(
        session_factory=fake_session_factory,
        evidence_service=evidence_service,
        publisher=publisher,
        operation_executor=executor,
    )

    result = await service.release_cycle(
        cycle_id="cycle-123",
        manual_approved=True,
    )

    assert result["status"] == "denied"

    assert (
        "release_disabled"
        in result["release_decision"]["reasons"]
    )

    assert len(evidence_service.calls) == 1
    assert publisher.channel_calls == 0
    assert publisher.privacy_calls == []
    assert executor.calls == []

    print(
        "PASS: default internal release policy "
        "fails closed before provider access."
    )


    # ========================================================
    # Enabled policy still requires manual approval
    # ========================================================

    policy = YoutubeReleasePolicy(
        enabled=True,
        min_production_score=70.0,
        require_manual_approval=True,
    )

    approval_evidence = FakeEvidenceService(
        build_evidence()
    )

    approval_publisher = FakePublisher()
    approval_executor = FakeExecutor()

    approval_service = YoutubeReleaseService(
        session_factory=fake_session_factory,
        evidence_service=approval_evidence,
        release_policy=policy,
        publisher=approval_publisher,
        operation_executor=approval_executor,
    )

    result = await approval_service.release_cycle(
        cycle_id="cycle-123",
        manual_approved=False,
    )

    assert result["status"] == "denied"

    assert (
        "manual_approval_required"
        in result["release_decision"]["reasons"]
    )

    assert approval_publisher.channel_calls == 0
    assert approval_publisher.privacy_calls == []
    assert approval_executor.calls == []

    print(
        "PASS: enabled release policy still "
        "requires manual approval."
    )


    # ========================================================
    # Low trusted production score cannot publish
    # ========================================================

    weak_evidence = FakeEvidenceService(
        build_evidence(
            score=69.0,
        )
    )

    weak_publisher = FakePublisher()
    weak_executor = FakeExecutor()

    weak_service = YoutubeReleaseService(
        session_factory=fake_session_factory,
        evidence_service=weak_evidence,
        release_policy=policy,
        publisher=weak_publisher,
        operation_executor=weak_executor,
    )

    result = await weak_service.release_cycle(
        cycle_id="cycle-123",
        manual_approved=True,
    )

    assert result["status"] == "denied"

    assert (
        "production_score_below_threshold"
        in result["release_decision"]["reasons"]
    )

    assert weak_publisher.channel_calls == 0
    assert weak_publisher.privacy_calls == []
    assert weak_executor.calls == []

    print(
        "PASS: low-score trusted evidence "
        "cannot publish."
    )


    # ========================================================
    # Valid trusted evidence crosses protected boundary
    # ========================================================

    valid_evidence = FakeEvidenceService(
        build_evidence()
    )

    valid_publisher = FakePublisher()
    valid_executor = FakeExecutor()

    valid_service = YoutubeReleaseService(
        session_factory=fake_session_factory,
        evidence_service=valid_evidence,
        release_policy=policy,
        publisher=valid_publisher,
        operation_executor=valid_executor,
    )

    result = await valid_service.release_cycle(
        cycle_id="cycle-123",
        manual_approved=True,
    )

    assert result["status"] == "completed"
    assert result["cycle_id"] == "cycle-123"
    assert result["video_id"] == "video-123"
    assert result["channel_id"] == "channel-123"
    assert result["privacy_status"] == "public"

    assert len(valid_evidence.calls) == 1

    assert (
        valid_evidence.calls[0]["cycle_id"]
        == "cycle-123"
    )

    assert valid_publisher.channel_calls == 1

    assert valid_publisher.privacy_calls == [
        {
            "video_id": "video-123",
            "privacy_status": "public",
        }
    ]

    assert len(valid_executor.calls) == 1

    operation = valid_executor.calls[0]

    assert (
        operation["operation_type"].value
        == "publish_video"
    )

    assert (
        operation["resource_id"]
        == "youtube-publish:channel-123:video-123"
    )

    print(
        "PASS: valid persisted evidence crosses "
        "the protected publication boundary."
    )

    print(
        "PASS: video identity came from trusted "
        "production evidence."
    )

    print(
        "PASS: channel identity came from "
        "authenticated provider state."
    )

    print(
        "PASS: PUBLISH_VIDEO idempotency "
        "boundary preserved."
    )


    # ========================================================
    # Replay cannot repeat provider transition
    # ========================================================

    replay_evidence = FakeEvidenceService(
        build_evidence()
    )

    replay_publisher = FakePublisher()
    replay_executor = ReplayExecutor()

    replay_service = YoutubeReleaseService(
        session_factory=fake_session_factory,
        evidence_service=replay_evidence,
        release_policy=policy,
        publisher=replay_publisher,
        operation_executor=replay_executor,
    )

    result = await replay_service.release_cycle(
        cycle_id="cycle-123",
        manual_approved=True,
    )

    assert result["status"] == "completed"
    assert result["publish"]["executed"] is False

    assert replay_publisher.channel_calls == 1
    assert replay_publisher.privacy_calls == []

    assert len(replay_executor.calls) == 1

    assert (
        replay_executor.calls[0]["resource_id"]
        == "youtube-publish:channel-123:video-123"
    )

    print(
        "PASS: idempotent replay does not "
        "repeat provider publication."
    )


    # ========================================================
    # Empty cycle identity fails before persistence access
    # ========================================================

    empty_evidence = FakeEvidenceService(
        build_evidence()
    )

    empty_service = YoutubeReleaseService(
        session_factory=fake_session_factory,
        evidence_service=empty_evidence,
        release_policy=policy,
        publisher=FakePublisher(),
        operation_executor=FakeExecutor(),
    )

    try:
        await empty_service.release_cycle(
            cycle_id="   ",
            manual_approved=True,
        )
    except ValueError as exc:
        assert (
            "cannot be empty"
            in str(exc).lower()
        )
    else:
        raise AssertionError(
            "Empty cycle identity must fail closed."
        )

    assert empty_evidence.calls == []

    print(
        "PASS: empty cycle identity fails "
        "before persistence access."
    )


    print()
    print(
        "PASS: internal YouTube release service "
        "regression suite complete."
    )


if __name__ == "__main__":
    asyncio.run(main())
