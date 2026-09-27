"""One bounded network work item per pass; durable state survives restart."""

from __future__ import annotations

import asyncio
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import select

from backend.models.network_allocation import NetworkAllocation
from backend.models.network_channel import NetworkChannel
from backend.models.network_control import NetworkControl
from backend.models.network_job import NetworkJob
from backend.services.network.job_store import ACTIVE_STATES, JobStore
from backend.services.runtime.execution_watchdog import run_bounded
from backend.services.runtime.capabilities import RuntimeCapabilityService


PROJECT_ROOT = Path(__file__).resolve().parents[3]


class NetworkSupervisor:
    def __init__(self, sessions, *, runner=run_bounded, root: Path = PROJECT_ROOT,
                 max_job_seconds: int = 7200, max_plan_seconds: int = 1200,
                 readiness=None):
        self.sessions, self.runner, self.root = sessions, runner, root
        self.max_job_seconds, self.max_plan_seconds = max_job_seconds, max_plan_seconds
        self.readiness = readiness or (lambda: RuntimeCapabilityService().inspect().missing_required)

    async def tick(self) -> dict:
        async with self.sessions() as db:
            control = await db.get(NetworkControl, "global")
            if control is None:
                control = NetworkControl(id="global")
                db.add(control)
                await db.commit()
                await db.refresh(control)
            if control.emergency_stop or not control.production_enabled:
                return {"status": "paused"}
            if shutil.disk_usage(self.root).free < control.min_free_bytes:
                return {"status": "disk_protection", "required_free_bytes": control.min_free_bytes}
            recovered = await JobStore().recover_stale(db)
            now = datetime.now(timezone.utc)
            if control.accept_new_jobs:
                channels = (await db.scalars(select(NetworkChannel).where(
                    NetworkChannel.lifecycle_state == "ACTIVE", NetworkChannel.paused.is_(False))
                    .order_by(NetworkChannel.id))).all()
                for channel in channels:
                    local_date = now.astimezone(ZoneInfo(channel.timezone)).date().isoformat()
                    allocation = await db.scalar(select(NetworkAllocation).where(
                        NetworkAllocation.channel_id == channel.id,
                        NetworkAllocation.local_date == local_date))
                    if allocation is None and channel.allowed_topics:
                        failure = (control.planner_failures or {}).get(channel.id, {})
                        until = failure.get("retry_after")
                        if until and datetime.fromisoformat(until) > now:
                            continue
                        return await self._execute("plan", channel.id, self.max_plan_seconds,
                                                   recovered=recovered)
            candidates = (await db.scalars(select(NetworkJob).where(
                NetworkJob.state.in_(("QUEUED", "REPAIR")))
                .order_by(NetworkJob.created_at, NetworkJob.id))).all()
            for job in candidates:
                if job.retry_after and job.retry_after.replace(tzinfo=timezone.utc) > now:
                    continue
                channel = await db.get(NetworkChannel, job.channel_id)
                if channel is None or channel.lifecycle_state != "ACTIVE" or channel.paused:
                    continue
                # Private, local QA does not need a YouTube token. All other
                # production dependencies remain required; never burn hours
                # repeatedly launching a known-incomplete runtime.
                missing = [name for name in self.readiness() if name != "youtube_token"]
                if missing:
                    return {"status": "runtime_unready", "missing_required": missing,
                            "job_id": job.id, "recovered": recovered}
                return await self._execute("job", job.id, self.max_job_seconds,
                                           recovered=recovered)
            return {"status": "idle", "recovered": recovered}

    async def _execute(self, kind: str, identifier: str, seconds: int,
                       *, recovered: list[str]) -> dict:
        script = "plan_network_day.py" if kind == "plan" else "run_network_job.py"
        command = [sys.executable, str(self.root / "scripts" / script), identifier]
        failure_type = None
        try:
            outcome = await asyncio.to_thread(
                self.runner, command, stage=f"network-{kind}", timeout_seconds=seconds,
                heartbeat_seconds=20, terminate_grace_seconds=5,
                log_path=self.root / "generated" / "logs" / f"network-{kind}.log",
                cwd=self.root)
            status = "completed" if outcome.returncode == 0 else "child_failed"
            if status == "child_failed":
                failure_type = "WorkerExit"
        except Exception as exc:
            status = "bounded_failure"
            failure_type = type(exc).__name__
        async with self.sessions() as db:
            if kind == "plan":
                control = await db.get(NetworkControl, "global")
                failures = dict(control.planner_failures or {})
                if status == "completed":
                    failures.pop(identifier, None)
                else:
                    count = int(failures.get(identifier, {}).get("count", 0)) + 1
                    failures[identifier] = {"count": count, "retry_after": (
                        datetime.now(timezone.utc) + timedelta(
                            seconds=min(3600, 300 * (2 ** min(count - 1, 4))))
                        ).isoformat(), "reason": failure_type}
                control.planner_failures = failures
                await db.commit()
            elif status != "completed":
                # Child may have persisted a repair already. If it died
                # unexpectedly, mark only its own active lease immediately.
                job = await db.get(NetworkJob, identifier)
                if job and job.state in ACTIVE_STATES:
                    job.attempt += 1
                    await db.commit()
                    await JobStore().transition(db, identifier,
                        "FAILED" if job.attempt >= job.max_attempts else "REPAIR",
                        reason=f"Bounded worker failure: {failure_type}")
        return {"status": status, "kind": kind, "id": identifier, "recovered": recovered}
