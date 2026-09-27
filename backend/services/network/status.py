"""Read-only operational snapshot with real database and filesystem values."""

from __future__ import annotations

import shutil
import os
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.human_action import HumanAction
from backend.models.network_allocation import NetworkAllocation
from backend.models.network_channel import NetworkChannel
from backend.models.network_control import NetworkControl
from backend.models.network_job import NetworkJob
from backend.models.youtube_performance_snapshot import YoutubePerformanceSnapshotRecord
from backend.services.runtime.capabilities import RuntimeCapabilityService


async def network_snapshot(db: AsyncSession, *, storage_path: Path) -> dict:
    control = await db.get(NetworkControl, "global")
    channels = (await db.scalars(select(NetworkChannel).order_by(NetworkChannel.name))).all()
    jobs = (await db.scalars(select(NetworkJob).order_by(NetworkJob.created_at.desc())
                             .limit(100))).all()
    pending = (await db.scalars(select(HumanAction).where(HumanAction.state == "OPEN")
                                .order_by(HumanAction.created_at))).all()
    allocations = (await db.scalars(select(NetworkAllocation)
                                    .order_by(NetworkAllocation.created_at.desc()).limit(100))).all()
    counts = (await db.execute(select(NetworkJob.state, func.count(NetworkJob.id))
                               .group_by(NetworkJob.state))).all()
    snapshots = (await db.scalars(select(YoutubePerformanceSnapshotRecord)
                                  .order_by(YoutubePerformanceSnapshotRecord.captured_at.desc())
                                  .limit(100))).all()
    disk = shutil.disk_usage(storage_path)
    return {
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "public_publishing_enabled": (
            os.environ.get("JARVIS_PUBLIC_PUBLISH_ENABLED", "").strip().lower() == "true"
        ),
        "controls": {
            "production_enabled": control.production_enabled if control else True,
            "accept_new_jobs": control.accept_new_jobs if control else True,
            "publishing_enabled": control.publishing_enabled if control else False,
            "emergency_stop": control.emergency_stop if control else False,
            "minimum_free_bytes": control.min_free_bytes if control else 5 * 1024**3,
            "planner_failures": control.planner_failures if control else {},
        },
        "channels": [{"id": c.id, "name": c.name, "handle": c.handle,
                      "production_engine": c.production_engine,
                      "niche": c.niche,
                      "lifecycle": c.lifecycle_state, "paused": c.paused,
                      "timezone": c.timezone, "max_daily_posts": c.max_daily_posts,
                      "youtube_channel_id": c.youtube_channel_id,
                      "capability": c.upload_capability,
                      "degraded_reason": c.degraded_reason} for c in channels],
        "jobs": [{"id": j.id, "channel_id": j.channel_id, "state": j.state,
                  "topic": j.topic, "attempt": j.attempt, "max_attempts": j.max_attempts,
                  "failure_reason": j.failure_reason,
                  "updated_at": j.updated_at.isoformat() if j.updated_at else None,
                  "retry_after": j.retry_after.isoformat() if j.retry_after else None,
                  "artifacts": j.artifacts, "lineage": j.lineage} for j in jobs],
        "job_counts": dict(counts),
        "allocations": [{"channel_id": a.channel_id, "local_date": a.local_date,
                         "target": a.target, "rationale": a.rationale,
                         "selected_job_ids": a.selected_job_ids} for a in allocations],
        "human_actions": [{"id": a.id, "kind": a.kind, "job_id": a.job_id,
                           "channel_id": a.channel_id, "what": a.what_happened,
                           "why": a.why_automation_stopped,
                           "required_user_action": a.required_user_action,
                           "resumes_afterward": a.resumes_afterward} for a in pending],
        "analytics": [{"channel_id": a.channel_id, "video_id": a.video_id,
                       "title": a.title, "views": a.views, "likes": a.likes,
                       "comments": a.comments,
                       "captured_at": a.captured_at.isoformat(),
                       "published_at": a.published_at.isoformat() if a.published_at else None}
                      for a in snapshots],
        "system": {"disk_total_bytes": disk.total, "disk_free_bytes": disk.free,
                   "ffmpeg_available": shutil.which("ffmpeg") is not None,
                   "cpu_percent": None, "ram_percent": None, "gpu_percent": None},
        "runtime_capabilities": RuntimeCapabilityService().inspect().as_dict(),
    }
