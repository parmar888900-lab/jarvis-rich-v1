"""YouTube agent handler."""

import asyncio
import hashlib
import logging
from pathlib import Path

from backend.database import async_session
from backend.services.agent_handlers.base import BaseAgentHandler
from backend.services.analytics.youtube_performance_collector import (
    YoutubePerformanceCollector,
)
from backend.services.analytics.youtube_performance_evidence_service import (
    YoutubePerformanceEvidenceService,
)
from backend.services.intelligence.production_selector import (
    ProductionTopicSelector,
)
from backend.services.intelligence.trend_engine import TrendEngine
from backend.services.orchestration.goal_production_strategy_service import (
    GoalProductionStrategyService,
)
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


logger = logging.getLogger(
    "jarvis.youtube.agent"
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

    def __init__(
        self,
        *,
        performance_collector=None,
        performance_evidence_service=None,
        goal_strategy_service=None,
        session_factory=None,
    ):
        self.engine = TrendEngine()
        self.selector = ProductionTopicSelector()
        self.pipeline = VideoPipeline()
        self.publisher = YoutubePublisher()

        self.performance_collector = (
            performance_collector
            or YoutubePerformanceCollector(
                publisher=self.publisher
            )
        )

        self.performance_evidence_service = (
            performance_evidence_service
            or YoutubePerformanceEvidenceService()
        )

        self.goal_strategy_service = (
            goal_strategy_service
            or GoalProductionStrategyService()
        )

        self.session_factory = (
            session_factory
            or async_session
        )

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

    async def _performance_evidence(
        self,
    ) -> tuple[
        dict | None,
        dict,
    ]:
        """
        Refresh channel analytics and build strategy evidence.

        Analytics is an optimization signal, not a production
        dependency. Provider or persistence failures therefore
        fail neutral and cannot block topic selection.
        """

        try:
            async with self.session_factory() as session:
                collection = (
                    await self.performance_collector.collect(
                        session,
                        max_items=50,
                    )
                )

                channel_id = str(
                    collection.get(
                        "channel_id",
                        "",
                    )
                ).strip()

                if not channel_id:
                    raise ValueError(
                        "Performance collection returned "
                        "an empty channel ID."
                    )

                evidence = (
                    await self.performance_evidence_service.build(
                        session,
                        channel_id,
                    )
                )

            return (
                evidence,
                {
                    "status": "success",
                    "channel_id": channel_id,
                    "collected_video_count": int(
                        collection.get(
                            "collected_video_count",
                            0,
                        )
                        or 0
                    ),
                    "snapshot_count": int(
                        collection.get(
                            "snapshot_count",
                            0,
                        )
                        or 0
                    ),
                    "unique_video_count": int(
                        evidence.get(
                            "unique_video_count",
                            0,
                        )
                        or 0
                    ),
                    "eligible_video_count": int(
                        evidence.get(
                            "video_count",
                            0,
                        )
                        or 0
                    ),
                    "total_views": int(
                        evidence.get(
                            "total_views",
                            0,
                        )
                        or 0
                    ),
                    "confidence": float(
                        evidence.get(
                            "confidence",
                            0.0,
                        )
                        or 0.0
                    ),
                    "strategy_ready": (
                        evidence.get(
                            "strategy_ready"
                        )
                        is True
                    ),
                },
            )

        except Exception as exc:
            logger.warning(
                "YouTube performance analytics "
                "unavailable; continuing with neutral "
                "historical evidence: %s",
                exc,
            )

            return (
                None,
                {
                    "status": "unavailable",
                    "strategy_ready": False,
                    "confidence": 0.0,
                    "error_type": type(
                        exc
                    ).__name__,
                },
            )

    async def _goal_strategy(
        self,
    ) -> tuple[
        dict,
        dict,
    ]:
        """
        Build production strategy from active goals.

        Goals are an optimization signal, not a production
        dependency. Goal persistence or evaluation failures
        therefore fail neutral and cannot block topic selection.

        Goal strategy does not control scheduler cadence.
        """

        try:
            async with self.session_factory() as session:
                strategy = (
                    await self.goal_strategy_service.build(
                        session
                    )
                )

            if not isinstance(strategy, dict):
                raise TypeError(
                    "Goal strategy service returned "
                    "a non-dictionary result."
                )

            status = str(
                strategy.get(
                    "status",
                    "neutral",
                )
            )

            return (
                strategy,
                {
                    "status": "success",
                    "strategy_status": status,
                    "goal_guided": (
                        status == "goal_guided"
                    ),
                    "active_goal_count": int(
                        strategy.get(
                            "active_goal_count",
                            0,
                        )
                        or 0
                    ),
                    "target_metric": (
                        strategy.get(
                            "target_metric"
                        )
                    ),
                    "trajectory": (
                        strategy.get(
                            "trajectory"
                        )
                    ),
                    "production_priority": float(
                        strategy.get(
                            "production_priority",
                            50.0,
                        )
                        or 0.0
                    ),
                    "exploration_bias": float(
                        strategy.get(
                            "exploration_bias",
                            0.5,
                        )
                        or 0.0
                    ),
                    "exploitation_bias": float(
                        strategy.get(
                            "exploitation_bias",
                            0.5,
                        )
                        or 0.0
                    ),
                    "scheduler_interval_multiplier": float(
                        strategy.get(
                            "scheduler_interval_multiplier",
                            1.0,
                        )
                        or 1.0
                    ),
                },
            )

        except Exception as exc:
            logger.warning(
                "Goal production strategy unavailable; "
                "continuing with neutral goal evidence: %s",
                exc,
            )

            neutral_strategy = {
                "status": "neutral",
                "active_goal_count": 0,
                "primary_goal": None,
                "target_metric": None,
                "trajectory": None,
                "urgency": 0.0,
                "production_priority": 50.0,
                "exploration_bias": 0.5,
                "exploitation_bias": 0.5,
                "scheduler_interval_multiplier": 1.0,
                "rationale": (
                    "Goal strategy unavailable; production "
                    "continues with neutral goal influence."
                ),
            }

            return (
                neutral_strategy,
                {
                    "status": "unavailable",
                    "strategy_status": "neutral",
                    "goal_guided": False,
                    "active_goal_count": 0,
                    "target_metric": None,
                    "trajectory": None,
                    "production_priority": 50.0,
                    "exploration_bias": 0.5,
                    "exploitation_bias": 0.5,
                    "scheduler_interval_multiplier": 1.0,
                    "error_type": type(
                        exc
                    ).__name__,
                },
            )

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

        (
            performance,
            analytics,
        ) = await self._performance_evidence()

        (
            goal_strategy,
            goal_strategy_status,
        ) = await self._goal_strategy()

        best_trend = self.selector.select(
            ranked_trends,
            performance=performance,
            goal_strategy=goal_strategy,
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
                "analytics": analytics,
                "goal_strategy": (
                    goal_strategy_status
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
            "analytics": analytics,
            "goal_strategy": (
                goal_strategy_status
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
        if privacy == "public":
            raise ValueError(
                "Direct public YouTube upload is forbidden. "
                "Upload privately, then use the protected "
                "release operation."
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
