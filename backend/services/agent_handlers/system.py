"""Read-only Jarvis system status agent."""

from __future__ import annotations

import json

from sqlalchemy import select

from backend.database import async_session
from backend.models.production_cycle import (
    ProductionCycleRecord,
    ProductionCycleStatus,
)
from backend.models.youtube_performance_snapshot import (
    YoutubePerformanceSnapshotRecord,
)
from backend.services.agent_handlers.base import BaseAgentHandler


class SystemAgentHandler(BaseAgentHandler):
    """Provide persisted Jarvis progress and analytics information."""

    name = "system"

    supported_tasks = frozenset(
        {
            "get_status",
        }
    )

    def __init__(
        self,
        *,
        session_factory=None,
    ) -> None:
        self.session_factory = (
            session_factory
            or async_session
        )

    async def execute(
        self,
        task: str,
        command_id: str,
        **kwargs,
    ) -> dict:

        if task != "get_status":
            raise ValueError(
                f"Unsupported system task: {task}"
            )

        status = await self._get_status()

        return {
            "agent": self.name,
            "task": task,
            "command_id": command_id,
            **status,
        }

    async def _get_status(self) -> dict:
        """Build a read-only snapshot from persisted state."""

        async with self.session_factory() as session:
            cycles_result = await session.execute(
                select(
                    ProductionCycleRecord
                ).order_by(
                    ProductionCycleRecord
                    .started_at
                    .desc()
                )
            )

            cycles = list(
                cycles_result.scalars().all()
            )

            snapshots_result = await session.execute(
                select(
                    YoutubePerformanceSnapshotRecord
                ).order_by(
                    YoutubePerformanceSnapshotRecord
                    .captured_at
                    .desc()
                )
            )

            snapshots = list(
                snapshots_result.scalars().all()
            )

        completed_cycles = sum(
            1
            for cycle in cycles
            if cycle.status
            == ProductionCycleStatus.COMPLETED
        )

        failed_cycles = sum(
            1
            for cycle in cycles
            if cycle.status
            == ProductionCycleStatus.FAILED
        )

        no_action_cycles = sum(
            1
            for cycle in cycles
            if cycle.status
            == ProductionCycleStatus.NO_ACTION
        )

        started_cycles = sum(
            1
            for cycle in cycles
            if cycle.status
            == ProductionCycleStatus.STARTED
        )

        latest_cycle = (
            cycles[0]
            if cycles
            else None
        )

        latest_cycle_data = None

        if latest_cycle is not None:
            parsed_result = None

            if latest_cycle.result:
                try:
                    parsed_result = json.loads(
                        latest_cycle.result
                    )
                except json.JSONDecodeError:
                    parsed_result = None

            latest_cycle_data = {
                "cycle_id": latest_cycle.id,
                "status": latest_cycle.status.value,
                "selected_topic": (
                    latest_cycle.selected_topic
                ),
                "production_score": (
                    latest_cycle.production_score
                ),
                "started_at": (
                    latest_cycle.started_at.isoformat()
                    if latest_cycle.started_at
                    else None
                ),
                "completed_at": (
                    latest_cycle.completed_at.isoformat()
                    if latest_cycle.completed_at
                    else None
                ),
                "result_status": (
                    parsed_result.get("status")
                    if isinstance(
                        parsed_result,
                        dict,
                    )
                    else None
                ),
            }

        latest_by_video = {}

        for snapshot in snapshots:
            if snapshot.video_id not in latest_by_video:
                latest_by_video[
                    snapshot.video_id
                ] = snapshot

        latest_snapshots = list(
            latest_by_video.values()
        )

        total_views = sum(
            int(snapshot.views or 0)
            for snapshot in latest_snapshots
        )

        total_likes = sum(
            int(snapshot.likes or 0)
            for snapshot in latest_snapshots
        )

        total_comments = sum(
            int(snapshot.comments or 0)
            for snapshot in latest_snapshots
        )

        private_videos = sum(
            1
            for snapshot in latest_snapshots
            if (
                snapshot.privacy_status
                or ""
            ).lower()
            == "private"
        )

        public_videos = sum(
            1
            for snapshot in latest_snapshots
            if (
                snapshot.privacy_status
                or ""
            ).lower()
            == "public"
        )

        latest_analytics_capture = (
            snapshots[0].captured_at.isoformat()
            if snapshots
            and snapshots[0].captured_at
            else None
        )

        latest_topic = (
            latest_cycle.selected_topic
            if latest_cycle is not None
            else None
        )

        latest_status = (
            latest_cycle.status.value
            if latest_cycle is not None
            else "none"
        )

        latest_score = (
            latest_cycle.production_score
            if latest_cycle is not None
            else None
        )

        score_text = (
            f"{latest_score:.1f}"
            if latest_score is not None
            else "n/a"
        )

        message = (
            "Jarvis status: "
            f"{completed_cycles} completed production cycles, "
            f"{len(latest_snapshots)} tracked YouTube videos, "
            f"{total_views} total views, "
            f"{total_likes} likes, "
            f"{total_comments} comments. "
            f"Latest production cycle is {latest_status}"
        )

        if latest_topic:
            message += (
                f" for '{latest_topic}'"
            )

        message += (
            f" with production score {score_text}."
        )

        return {
            "status": "success",
            "message": message,
            "production": {
                "total_cycles": len(cycles),
                "completed_cycles": (
                    completed_cycles
                ),
                "failed_cycles": (
                    failed_cycles
                ),
                "no_action_cycles": (
                    no_action_cycles
                ),
                "started_cycles": (
                    started_cycles
                ),
                "latest_cycle": (
                    latest_cycle_data
                ),
            },
            "youtube": {
                "tracked_video_count": (
                    len(latest_snapshots)
                ),
                "snapshot_count": (
                    len(snapshots)
                ),
                "total_views": total_views,
                "total_likes": total_likes,
                "total_comments": (
                    total_comments
                ),
                "private_video_count": (
                    private_videos
                ),
                "public_video_count": (
                    public_videos
                ),
                "latest_capture_at": (
                    latest_analytics_capture
                ),
            },
        }
