"""YouTube agent handler."""

from backend.services.agent_handlers.base import BaseAgentHandler
from backend.services.intelligence.trend_engine import TrendEngine
from backend.services.providers.registry import build_trend_manager
from backend.services.pipelines import VideoPipeline


class YoutubeAgentHandler(BaseAgentHandler):
    """
    Handles YouTube automation tasks.

    Responsibilities:
        - Collect trends
        - Rank trends
        - Launch the VideoPipeline

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

        self.pipeline = VideoPipeline()

    async def execute(
        self,
        task: str,
        command_id: str,
        **kwargs,
    ) -> dict:

        if task == "analyze_trends":
            return await self._analyze_trends(command_id)

        if task == "create_video":
            return await self._create_video(command_id)

        if task == "upload_video":
            return await self._upload_video(command_id)

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

        best_trend = ranked_trends[0]

        ###################################################
        # Entire video generation happens here
        ###################################################

        result = await self.pipeline.run(
            best_trend
        )

        ###################################################

        return {
            "agent": self.name,
            "task": "analyze_trends",
            "command_id": command_id,
            "provider_count": len(manager.providers),
            "raw_trend_count": len(raw_trends),
            "final_trend_count": len(ranked_trends),
            "best_trend": best_trend,
            "generated_content": result["generated"].to_dict(),
            "production_package": result["production_package"],
            "status": "success",
        }

    async def _create_video(
        self,
        command_id: str,
    ) -> dict:

        return {
            "status": "coming_soon",
            "command_id": command_id,
        }

    async def _upload_video(
        self,
        command_id: str,
    ) -> dict:

        return {
            "status": "coming_soon",
            "command_id": command_id,
        }