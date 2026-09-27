"""Run a durable network job through the existing Rich V1 engine, stopping at QA.

The caller must run this worker inside the process-tree watchdog. It does not
mark perceptual quality approved and it never invokes an upload endpoint.
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy.ext.asyncio import async_sessionmaker

from backend.models.network_job import NetworkJob
from backend.services.network.job_store import JobStore


class ProductionBridge:
    def __init__(self, session_factory: async_sessionmaker, *, orchestrator=None,
                 job_store: JobStore | None = None):
        self.sessions = session_factory
        if orchestrator is None:
            from backend.services.orchestration.production_orchestrator import ProductionOrchestrator
            orchestrator = ProductionOrchestrator(
                session_factory=session_factory, private_upload_enabled=False)
        self.orchestrator = orchestrator
        self.jobs = job_store or JobStore()
        self._requires_selected_trend = orchestrator is None

    async def run(self, job_id: str, *, worker_id: str, lease_seconds: int = 7200) -> dict:
        async with self.sessions() as session:
            job = await session.get(NetworkJob, job_id)
            if job is None:
                raise LookupError("Production job not found")
            if job.state not in {"QUEUED", "REPAIR"}:
                raise ValueError("Only queued or repair jobs may start a production cycle")
            selected_trend = job.scheduler_decision.get("selected_trend")
            if self._requires_selected_trend and not isinstance(selected_trend, dict):
                raise ValueError("Network job lacks a channel-vetted selected trend")
            if isinstance(selected_trend, dict) and selected_trend.get("title") != job.topic:
                raise ValueError("Selected trend does not match reserved job topic")
            attempt = job.attempt
            await self.jobs.start_stage(session, job_id, "RESEARCHING", worker_id,
                                        lease_seconds=lease_seconds)

        # The existing orchestrator owns research, selection and actual video
        # production. Stable cycle identity makes its own operations idempotent.
        try:
            cycle_id = f"network:{job_id}:attempt:{attempt}"
            if isinstance(selected_trend, dict):
                result = await self.orchestrator.run_cycle(cycle_id,
                                                           selected_trend=selected_trend)
            else:
                result = await self.orchestrator.run_cycle(cycle_id)
        except Exception as exc:
            async with self.sessions() as session:
                job = await session.get(NetworkJob, job_id)
                job.attempt += 1
                await session.commit()
                await self.jobs.transition(session, job_id,
                                           "FAILED" if job.attempt >= job.max_attempts else "REPAIR",
                                           reason=f"Production error: {type(exc).__name__}")
            raise

        async with self.sessions() as session:
            job = await session.get(NetworkJob, job_id)
            job.last_result = result
            await session.commit()
            if result.get("status") == "no_action":
                await self.jobs.transition(session, job_id, "COMPLETE",
                                           reason="No eligible evidence-backed topic")
                return result
            path = result.get("video_path")
            if result.get("status") != "awaiting_qa" or not isinstance(path, str) or not Path(path).is_file():
                job.attempt += 1
                await session.commit()
                await self.jobs.transition(session, job_id,
                                           "FAILED" if job.attempt >= job.max_attempts else "REPAIR",
                                           reason="No verified local render reached QA")
                return result
            await self.jobs.transition(session, job_id, "QA", artifact=("render", path),
                                       lineage={"production_cycle": f"network:{job_id}:attempt:{attempt}"})
            return result
