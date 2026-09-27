"""Run a durable network job through the existing Rich V1 engine, stopping at QA.

The caller must run this worker inside the process-tree watchdog. It does not
mark perceptual quality approved and it never invokes an upload endpoint.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from backend.models.network_channel import NetworkChannel
from backend.models.network_identity import NetworkContentIdentity
from backend.models.network_job import NetworkJob
from backend.services.network.job_store import JobStore


def verify_local_render(path: Path) -> bool:
    """Check actual decodable stream metadata before recording a QA artifact.

    This is technical admission to human/perceptual QA, never an approval.
    """
    if not path.is_file() or path.stat().st_size == 0:
        return False
    try:
        completed = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries",
             "format=duration:stream=codec_type,width,height", "-of", "json", str(path)],
            capture_output=True, text=True, timeout=20, check=False,
        )
        if completed.returncode != 0:
            return False
        probe = json.loads(completed.stdout)
        duration = float(probe.get("format", {}).get("duration", 0))
        streams = probe.get("streams", [])
        return (0 < duration <= 180 and any(s.get("codec_type") == "audio" for s in streams)
                and any(s.get("codec_type") == "video" and s.get("width", 0) > 0
                        and s.get("height", 0) > 0 for s in streams))
    except (OSError, ValueError, TypeError, json.JSONDecodeError, subprocess.TimeoutExpired):
        return False


class ProductionBridge:
    def __init__(self, session_factory: async_sessionmaker, *, orchestrator=None,
                 job_store: JobStore | None = None, render_verifier=verify_local_render):
        self.sessions = session_factory
        self._requires_selected_trend = orchestrator is None
        if orchestrator is None:
            from backend.services.orchestration.production_orchestrator import ProductionOrchestrator
            orchestrator = ProductionOrchestrator(
                session_factory=session_factory, private_upload_enabled=False)
        self.orchestrator = orchestrator
        self.jobs = job_store or JobStore()
        self.render_verifier = render_verifier

    async def run(self, job_id: str, *, worker_id: str, lease_seconds: int = 7200) -> dict:
        async with self.sessions() as session:
            job = await session.get(NetworkJob, job_id)
            if job is None:
                raise LookupError("Production job not found")
            if job.state not in {"QUEUED", "REPAIR"}:
                raise ValueError("Only queued or repair jobs may start a production cycle")
            channel = await session.get(NetworkChannel, job.channel_id)
            if channel is None or channel.paused or channel.lifecycle_state != "ACTIVE":
                raise ValueError("Paused or inactive channel cannot execute")
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
            # Handler derives its content identity from the prefix before
            # the first colon. Keep the job UUID in that prefix.
            cycle_id = f"network-{job_id}-attempt-{attempt}"
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
            if (result.get("status") != "awaiting_qa" or not isinstance(path, str)
                    or not self.render_verifier(Path(path))):
                job.attempt += 1
                await session.commit()
                await self.jobs.transition(session, job_id,
                                           "FAILED" if job.attempt >= job.max_attempts else "REPAIR",
                                           reason="No verified local render reached QA")
                return result
            digest = hashlib.sha256()
            with Path(path).open("rb") as handle:
                for block in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(block)
            video_sha256 = digest.hexdigest()
            duplicate = await session.scalar(select(NetworkContentIdentity).where(
                NetworkContentIdentity.render_sha256 == video_sha256,
                NetworkContentIdentity.job_id != job_id))
            if duplicate:
                job.attempt += 1
                await session.commit()
                await self.jobs.transition(session, job_id,
                    "FAILED" if job.attempt >= job.max_attempts else "REPAIR",
                    reason=f"Duplicate final render conflicts with job {duplicate.job_id}")
                return result
            identity = await session.scalar(select(NetworkContentIdentity).where(
                NetworkContentIdentity.job_id == job_id))
            if identity:
                identity.render_sha256 = video_sha256
                identity.title = str(result.get("selected_trend", {}).get("title") or "") or None
            package = result.get("production", {}).get("production_package", {})
            package_dir = Path(package.get("package_dir", "")) if isinstance(package, dict) else None
            script_hash = None
            if package_dir and (package_dir / "script.txt").is_file():
                script = (package_dir / "script.txt").read_text(encoding="utf-8")
                script_hash = hashlib.sha256(script.encode("utf-8")).hexdigest()
                if identity:
                    identity.script = script
            evidence_ids = []
            if package_dir and (package_dir / "metadata.json").is_file():
                metadata = json.loads((package_dir / "metadata.json").read_text(encoding="utf-8"))
                evidence_ids = metadata.get("metadata", {}).get("evidence_ids", [])
            await session.commit()
            await self.jobs.transition(session, job_id, "QA", artifact=("render", path),
                                       lineage={"production_cycle": cycle_id,
                                                "render_sha256": video_sha256,
                                                "package_dir": str(package_dir) if package_dir else None,
                                                "script_sha256": script_hash,
                                                "evidence_ids": evidence_ids})
            return result
