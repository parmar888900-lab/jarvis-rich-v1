"""Transactional persistent job transitions and bounded crash recovery."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.network_channel import NetworkChannel
from backend.models.network_job import JOB_STATES, NetworkJob, NetworkJobEvent


ACTIVE_STATES = frozenset({
    "RESEARCHING", "SCRIPTING", "VISUAL_PLANNING", "MEDIA_RESOLVING",
    "NARRATING", "EDITING", "RENDERING", "QA", "REPAIR", "UPLOADING",
})
TERMINAL_STATES = frozenset({"COMPLETE", "FAILED"})
ALLOWED = {
    "QUEUED": {"RESEARCHING", "WAITING_FOR_QUOTA", "WAITING_FOR_SCHEDULE", "FAILED"},
    # The existing Rich V1 production engine encapsulates its internal stages.
    # The bridge records only milestones it can actually observe.
    "RESEARCHING": {"EVIDENCE_READY", "QA", "COMPLETE", "REPAIR", "FAILED", "HUMAN_ACTION_REQUIRED"},
    "EVIDENCE_READY": {"SCRIPTING", "REPAIR", "FAILED"},
    "SCRIPTING": {"SCRIPTED", "REPAIR", "FAILED"},
    "SCRIPTED": {"VISUAL_PLANNING", "REPAIR", "FAILED"},
    "VISUAL_PLANNING": {"MEDIA_RESOLVING", "REPAIR", "FAILED"},
    "MEDIA_RESOLVING": {"MEDIA_READY", "REPAIR", "FAILED", "HUMAN_ACTION_REQUIRED"},
    "MEDIA_READY": {"NARRATING", "REPAIR", "FAILED"},
    "NARRATING": {"EDITING", "REPAIR", "FAILED"},
    "EDITING": {"RENDERING", "REPAIR", "FAILED"},
    "RENDERING": {"QA", "REPAIR", "FAILED"},
    "QA": {"APPROVED", "REPAIR", "FAILED"},
    "REPAIR": {"RESEARCHING", "SCRIPTING", "MEDIA_RESOLVING", "RENDERING", "QA", "FAILED"},
    "APPROVED": {"WAITING_FOR_QUOTA", "WAITING_FOR_SCHEDULE", "COMPLETE", "FAILED"},
    "WAITING_FOR_QUOTA": {"QUEUED", "WAITING_FOR_SCHEDULE", "FAILED"},
    "WAITING_FOR_SCHEDULE": {"QUEUED", "UPLOADING", "COMPLETE", "FAILED"},
    "UPLOADING": {"SCHEDULED", "PUBLISHED", "HUMAN_ACTION_REQUIRED", "FAILED"},
    "SCHEDULED": {"PUBLISHED", "HUMAN_ACTION_REQUIRED", "FAILED"},
    "PUBLISHED": {"ANALYTICS_PENDING", "COMPLETE"},
    "ANALYTICS_PENDING": {"COMPLETE", "FAILED"},
    "HUMAN_ACTION_REQUIRED": {"QUEUED", "WAITING_FOR_SCHEDULE", "FAILED"},
    "COMPLETE": set(), "FAILED": set(),
}
assert set(ALLOWED) == JOB_STATES


class JobStore:
    async def enqueue(self, session: AsyncSession, *, channel_id: str,
                      idempotency_key: str, topic: str | None = None,
                      scheduler_decision: dict | None = None) -> NetworkJob:
        key = idempotency_key.strip()
        if not key or len(key) > 180:
            raise ValueError("Idempotency key must be 1–180 characters")
        existing = await session.scalar(select(NetworkJob).where(NetworkJob.idempotency_key == key))
        if existing:
            if existing.channel_id != channel_id or existing.topic != topic:
                raise ValueError("Idempotency key belongs to a different production request")
            return existing
        channel = await session.get(NetworkChannel, channel_id)
        if channel is None:
            raise LookupError("Channel not registered")
        if channel.paused or channel.lifecycle_state != "ACTIVE":
            raise ValueError("Channel is not active for production")
        job = NetworkJob(channel_id=channel_id, idempotency_key=key,
                         production_engine=channel.production_engine, topic=topic,
                         topic_key=" ".join((topic or "").casefold().split()) or None,
                         scheduler_decision=scheduler_decision or {})
        session.add(job)
        try:
            await session.flush()
            session.add(NetworkJobEvent(job_id=job.id, from_state=None,
                                        to_state="QUEUED", attempt=0))
            await session.commit()
        except IntegrityError:
            await session.rollback()
            found = await session.scalar(select(NetworkJob).where(NetworkJob.idempotency_key == key))
            if found and found.channel_id == channel_id and found.topic == topic:
                return found
            raise ValueError("Conflicting idempotent production request") from None
        await session.refresh(job)
        return job

    async def transition(self, session: AsyncSession, job_id: str, state: str,
                         *, reason: str | None = None,
                         artifact: tuple[str, str] | None = None,
                         lineage: dict | None = None) -> NetworkJob:
        if state not in JOB_STATES:
            raise ValueError("Unknown production job state")
        job = await session.get(NetworkJob, job_id)
        if job is None:
            raise LookupError("Production job not found")
        if state not in ALLOWED[job.state]:
            raise ValueError(f"Illegal production transition {job.state} to {state}")
        if state == "APPROVED" and not (job.artifacts or artifact):
            raise ValueError("Cannot approve without a recorded QA artifact")
        previous = job.state
        job.state = state
        job.worker_id = None
        job.lease_until = None
        job.failure_reason = reason if state in {"FAILED", "HUMAN_ACTION_REQUIRED"} else None
        job.retry_after = (datetime.now(timezone.utc) + timedelta(
            seconds=min(3600, 60 * (2 ** min(job.attempt, 6))))) if state == "REPAIR" else None
        if artifact:
            if not all(artifact):
                raise ValueError("Artifact type and path are required")
            job.artifacts = {**job.artifacts, artifact[0]: artifact[1]}
        if lineage:
            job.lineage = {**job.lineage, **lineage}
        if state in TERMINAL_STATES:
            job.completed_at = datetime.now(timezone.utc)
        session.add(NetworkJobEvent(job_id=job.id, from_state=previous, to_state=state,
                                    attempt=job.attempt, reason=reason))
        await session.commit()
        await session.refresh(job)
        return job

    async def recover_stale(self, session: AsyncSession, *, at: datetime | None = None) -> list[str]:
        """Mark expired stage leases for bounded repair, leaving other jobs alone."""
        now = at or datetime.now(timezone.utc)
        rows = await session.scalars(select(NetworkJob).where(NetworkJob.state.in_(ACTIVE_STATES)))
        recovered = []
        for job in rows:
            if job.lease_until is None or job.lease_until.replace(tzinfo=timezone.utc) > now:
                continue
            previous = job.state
            job.worker_id = None
            job.lease_until = None
            job.attempt += 1
            job.state = "FAILED" if job.attempt >= job.max_attempts else "REPAIR"
            job.failure_reason = f"Worker lease expired during {previous}"
            job.retry_after = (now + timedelta(seconds=min(3600, 60 * (2 ** min(job.attempt, 6))))) \
                if job.state == "REPAIR" else None
            session.add(NetworkJobEvent(job_id=job.id, from_state=previous,
                                        to_state=job.state, attempt=job.attempt,
                                        reason=job.failure_reason))
            recovered.append(job.id)
        await session.commit()
        return recovered

    async def start_stage(self, session: AsyncSession, job_id: str, state: str,
                          worker_id: str, *, lease_seconds: int = 900) -> NetworkJob:
        if state not in ACTIVE_STATES or not worker_id.strip() or not 30 <= lease_seconds <= 7200:
            raise ValueError("Active stage, worker ID and bounded lease required")
        job = await session.get(NetworkJob, job_id)
        if job is None:
            raise LookupError("Production job not found")
        if state not in ALLOWED[job.state]:
            raise ValueError(f"Illegal production transition {job.state} to {state}")
        previous = job.state
        job.state = state
        job.worker_id = worker_id.strip()
        job.lease_until = datetime.now(timezone.utc) + timedelta(seconds=lease_seconds)
        session.add(NetworkJobEvent(job_id=job.id, from_state=previous, to_state=state,
                                    attempt=job.attempt))
        await session.commit()
        return job

    async def heartbeat(self, session: AsyncSession, job_id: str, worker_id: str,
                        *, lease_seconds: int = 900) -> NetworkJob:
        job = await session.get(NetworkJob, job_id)
        if job is None or job.worker_id != worker_id or job.state not in ACTIVE_STATES:
            raise ValueError("No active lease held by this worker")
        if not 30 <= lease_seconds <= 7200:
            raise ValueError("Bounded lease required")
        job.lease_until = datetime.now(timezone.utc) + timedelta(seconds=lease_seconds)
        await session.commit()
        return job
