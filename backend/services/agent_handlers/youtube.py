"""YouTube agent handler."""

import asyncio
import hashlib
from pathlib import Path

from backend.database import async_session
from backend.services.agent_handlers.base import BaseAgentHandler
from backend.services.intelligence.production_selector import (
    ProductionTopicSelector,
)
from backend.services.intelligence.trend_engine import TrendEngine
from backend.services.providers.registry import build_trend_manager
from backend.services.orchestration.idempotency import (
    OperationType,
    build_idempotency_key,
)
from backend.services.orchestration.idempotent_operation_executor import (
    IdempotentOperationExecutor,
)
from backend.services.pipelines import VideoPipeline
from backend.services.providers.youtube_publisher import (
    YoutubePublisher,
    build_youtube_operation_tag,
)


class YoutubeAgentHandler(BaseAgentHandler):
    """
    Handles YouTube automation tasks.

    Responsibilities:
        - Collect trends
        - Rank trends
        - Select production-ready topics
        - Launch the VideoPipeline for create_video

    It should NEVER know how videos are built.
    """

    name = "youtube"

    supported_tasks = frozenset(
        {
            "analyze_trends",
            "create_video",
            "upload_video",
        }
    )

    def __init__(self):
        self.engine = TrendEngine()
        self.selector = ProductionTopicSelector()
        self.pipeline = VideoPipeline()
        self.publisher = YoutubePublisher()
        self.operation_executor = (
            IdempotentOperationExecutor(
                async_session
            )
        )

    async def execute(
        self,
        task: str,
        command_id: str,
        **kwargs,
    ) -> dict:

        if task == "analyze_trends":
            return await self._analyze_trends(
                command_id
            )

        if task == "create_video":
            return await self._create_video(
                command_id,
                **kwargs,
            )

        if task == "upload_video":
            return await self._upload_video(
                command_id,
                **kwargs,
            )

        return {
            "status": "unsupported_task",
            "task": task,
        }

    async def _analyze_trends(
        self,
        command_id: str,
    ) -> dict:

        manager = build_trend_manager()

        raw_trends = manager.collect_candidates(
            per_provider_limit=25,
        )

        ranked_trends = self.engine.process(
            raw_trends,
            limit=10,
        )

        if not ranked_trends:
            return {
                "agent": self.name,
                "task": "analyze_trends",
                "command_id": command_id,
                "status": "no_trends_found",
            }

        best_trend = self.selector.select(
            ranked_trends
        )

        if best_trend is None:
            return {
                "agent": self.name,
                "task": "analyze_trends",
                "command_id": command_id,
                "provider_count": len(
                    manager.providers
                ),
                "raw_trend_count": len(
                    raw_trends
                ),
                "final_trend_count": len(
                    ranked_trends
                ),
                "status": (
                    "no_production_ready_topic"
                ),
            }

        return {
            "agent": self.name,
            "task": "analyze_trends",
            "command_id": command_id,
            "provider_count": len(
                manager.providers
            ),
            "raw_trend_count": len(
                raw_trends
            ),
            "final_trend_count": len(
                ranked_trends
            ),
            "best_trend": best_trend,
            "status": "success",
        }

    async def _create_video(
        self,
        command_id: str,
        **kwargs,
    ) -> dict:

        trend = kwargs.get("trend")

        if not isinstance(trend, dict):
            return {
                "agent": self.name,
                "task": "create_video",
                "command_id": command_id,
                "status": "invalid_parameters",
                "error": (
                    "create_video requires a "
                    "trend dictionary."
                ),
            }

        title = str(
            trend.get("title", "")
        ).strip()

        if not title:
            return {
                "agent": self.name,
                "task": "create_video",
                "command_id": command_id,
                "status": "invalid_parameters",
                "error": (
                    "trend.title is required."
                ),
            }

        result = await self.pipeline.run(
            trend
        )

        return {
            "agent": self.name,
            "task": "create_video",
            "command_id": command_id,
            "trend": trend,
            "generated_content": (
                result["generated"].to_dict()
            ),
            "production_package": (
                result["production_package"]
            ),
            "video": (
                result["video"]
            ),
            "status": "success",
        }

    @staticmethod
    def _sha256_file(
        path: Path,
    ) -> str:
        """Return a stable SHA-256 identity for a video."""

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

    async def _upload_video(
        self,
        command_id: str,
        *,
        video_path: str,
        title: str,
        description: str = "",
        tags: list[str] | None = None,
        privacy_status: str = "private",
        category_id: str = "22",
        allow_public: bool = False,
    ) -> dict:
        """Upload a video through the idempotent boundary."""

        path = Path(
            video_path
        ).expanduser().resolve()

        if not path.is_file():
            raise FileNotFoundError(
                f"Video not found: {path}"
            )

        clean_title = title.strip()

        if not clean_title:
            raise ValueError(
                "YouTube title cannot be empty."
            )

        privacy = (
            privacy_status
            .strip()
            .lower()
        )

        allowed_privacy = {
            "private",
            "unlisted",
            "public",
        }

        if privacy not in allowed_privacy:
            raise ValueError(
                "privacy_status must be private, "
                "unlisted, or public."
            )

        # Public publishing stays fail-closed until
        # the autonomous release policy is added.
        if (
            privacy == "public"
            and not allow_public
        ):
            raise ValueError(
                "Public YouTube publishing is locked. "
                "Set allow_public=true only through an "
                "authorized release policy."
            )

        clean_tags = []

        for tag in tags or []:
            clean_tag = str(
                tag
            ).strip()

            if clean_tag:
                clean_tags.append(
                    clean_tag
                )

        channel = await asyncio.to_thread(
            self.publisher
            .get_authorized_channel
        )

        video_hash = await asyncio.to_thread(
            self._sha256_file,
            path,
        )

        resource_id = (
            f"youtube:"
            f"{channel['channel_id']}:"
            f"{video_hash}"
        )

        idempotency_key = (
            build_idempotency_key(
                OperationType.UPLOAD_VIDEO,
                resource_id,
            )
        )

        operation_tag = (
            build_youtube_operation_tag(
                idempotency_key
            )
        )

        async def upload() -> dict:
            return await self.publisher.upload_video(
                video_path=path,
                title=clean_title,
                description=description,
                tags=clean_tags,
                privacy_status=privacy,
                category_id=str(
                    category_id
                ),
                operation_tag=operation_tag,
            )

        operation_result = (
            await self.operation_executor.execute(
                operation_type=(
                    OperationType.UPLOAD_VIDEO
                ),
                resource_id=resource_id,
                operation=upload,
            )
        )

        return {
            "agent": self.name,
            "task": "upload_video",
            "command_id": command_id,
            "status": (
                operation_result["status"]
            ),
            "channel_id": (
                channel["channel_id"]
            ),
            "channel_title": (
                channel["channel_title"]
            ),
            "artifact_sha256": video_hash,
            "privacy_status": privacy,
            "upload": operation_result,
        }
