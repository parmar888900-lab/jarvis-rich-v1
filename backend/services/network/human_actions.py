"""Record user-only blockers without freezing unrelated jobs."""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.human_action import HumanAction
from backend.models.network_job import NetworkJob
from backend.services.network.job_store import JobStore


class HumanActionQueue:
    async def open(self, db: AsyncSession, *, kind: str, what: str, why: str,
                   user_action: str, resume: str, channel_id: str | None = None,
                   job_id: str | None = None) -> HumanAction:
        if not all(x.strip() for x in (kind, what, why, user_action, resume)):
            raise ValueError("Human action needs what, why, user step, and resume step")
        if job_id:
            job = await db.get(NetworkJob, job_id)
            if job is None:
                raise LookupError("Job not found")
            if channel_id and job.channel_id != channel_id:
                raise ValueError("Blocker channel does not match job")
            channel_id = job.channel_id
            if job.state in {"RESEARCHING", "MEDIA_RESOLVING", "UPLOADING", "SCHEDULED"}:
                await JobStore().transition(db, job_id, "HUMAN_ACTION_REQUIRED", reason=why)
        record = HumanAction(kind=kind, what_happened=what,
                             why_automation_stopped=why,
                             required_user_action=user_action,
                             resumes_afterward=resume,
                             channel_id=channel_id, job_id=job_id)
        db.add(record)
        await db.commit()
        await db.refresh(record)
        return record

    async def pending(self, db: AsyncSession) -> list[HumanAction]:
        return list((await db.scalars(select(HumanAction).where(
            HumanAction.state == "OPEN").order_by(HumanAction.created_at))).all())

    async def resolve(self, db: AsyncSession, action_id: str) -> HumanAction:
        record = await db.get(HumanAction, action_id)
        if record is None:
            raise LookupError("Human action not found")
        if record.state != "OPEN":
            return record
        record.state = "RESOLVED"
        record.resolved_at = datetime.now(timezone.utc)
        await db.commit()
        # Resolution only records the owner action. Revalidation of OAuth,
        # copyright or account capability must precede job resumption.
        return record
