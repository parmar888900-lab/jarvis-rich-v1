"""Internal protected service for releasing private YouTube uploads."""

from __future__ import annotations

import asyncio

from backend.database import async_session
from backend.services.orchestration.idempotency import (
    OperationType,
)
from backend.services.orchestration.idempotent_operation_executor import (
    IdempotentOperationExecutor,
)
from backend.services.orchestration.youtube_release_evidence import (
    YoutubeReleaseEvidenceService,
)
from backend.services.orchestration.youtube_release_policy import (
    YoutubeReleasePolicy,
)
from backend.services.providers.youtube_publisher import (
    YoutubePublisher,
)


class YoutubeReleaseService:
    """
    Protected internal boundary for private-to-public publication.

    This service is deliberately separate from Commander and the generic
    YouTube agent. Public release must therefore not be reachable merely by
    submitting arbitrary command parameters.
    """

    def __init__(
        self,
        *,
        session_factory=None,
        evidence_service=None,
        release_policy=None,
        publisher=None,
        operation_executor=None,
    ) -> None:
        self.session_factory = (
            session_factory
            or async_session
        )

        self.evidence_service = (
            evidence_service
            or YoutubeReleaseEvidenceService()
        )

        self.release_policy = (
            release_policy
            or YoutubeReleasePolicy()
        )

        self.publisher = (
            publisher
            or YoutubePublisher()
        )

        self.operation_executor = (
            operation_executor
            or IdempotentOperationExecutor(
                async_session
            )
        )

    async def release_cycle(
        self,
        *,
        cycle_id: str,
        manual_approved: bool = False,
    ) -> dict:
        clean_cycle_id = str(
            cycle_id or ""
        ).strip()

        if not clean_cycle_id:
            raise ValueError(
                "cycle_id cannot be empty."
            )

        async with self.session_factory() as session:
            cycle_result = (
                await self.evidence_service.resolve(
                    session,
                    cycle_id=clean_cycle_id,
                )
            )

        decision = self.release_policy.evaluate(
            cycle_result=cycle_result,
            manual_approved=manual_approved,
        )

        if decision.get("authorized") is not True:
            return {
                "status": "denied",
                "cycle_id": clean_cycle_id,
                "release_decision": decision,
            }

        video_id = str(
            decision.get(
                "video_id",
                "",
            )
        ).strip()

        target_privacy_status = str(
            decision.get(
                "target_privacy_status",
                "",
            )
        ).strip().lower()

        if not video_id:
            raise ValueError(
                "Authorized release decision is missing "
                "the YouTube video identity."
            )

        if target_privacy_status != "public":
            raise ValueError(
                "Authorized release decision does not "
                "target PUBLIC visibility."
            )

        channel = await asyncio.to_thread(
            self.publisher.get_authorized_channel
        )

        channel_id = str(
            channel.get(
                "channel_id",
                "",
            )
        ).strip()

        if not channel_id:
            raise ValueError(
                "Authorized YouTube channel identity "
                "is unavailable."
            )

        resource_id = (
            f"youtube-publish:{channel_id}:"
            f"{video_id}"
        )

        async def publish() -> dict:
            return await self.publisher.set_video_privacy(
                video_id=video_id,
                privacy_status="public",
            )

        operation_result = (
            await self.operation_executor.execute(
                operation_type=(
                    OperationType.PUBLISH_VIDEO
                ),
                resource_id=resource_id,
                operation=publish,
            )
        )

        return {
            "status": operation_result["status"],
            "cycle_id": clean_cycle_id,
            "channel_id": channel_id,
            "video_id": video_id,
            "privacy_status": "public",
            "release_decision": decision,
            "publish": operation_result,
        }
