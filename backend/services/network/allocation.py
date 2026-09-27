"""Evidence-first 0–4 per-channel daily allocation with durable decisions."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.network_allocation import NetworkAllocation
from backend.models.network_channel import NetworkChannel
from backend.models.network_job import NetworkJob
from backend.services.network.job_store import JobStore
from backend.services.network.originality import DuplicateContentError, OriginalityGate


def _score(item: dict) -> float:
    values = [item.get(k) for k in ("quality", "evidence", "visual", "originality")]
    if any(isinstance(v, bool) or not isinstance(v, (float, int)) or not 0 <= v <= 1
           for v in values):
        raise ValueError("Candidate needs measured quality, evidence, visual and originality scores")
    # Weakest evidence/visual signal governs production; do not average it away.
    return min(values)


class PreviouslyRejectedCommission(ValueError):
    """The same topic already has a durable failed commissioning attempt."""


class DailyAllocator:
    async def commission_one(self, session: AsyncSession, *, channel_id: str,
                             candidate: dict, at: datetime | None = None) -> NetworkJob:
        """Audited one-off QA job without altering a sealed daily allocation.

        Intended for commissioning after a planning defect is repaired. It
        retains all editorial, opportunity, capacity and originality gates.
        """
        channel = await session.get(NetworkChannel, channel_id)
        if channel is None or channel.lifecycle_state != "ACTIVE" or channel.paused:
            raise ValueError("Channel is not active")
        now = at or datetime.now(timezone.utc)
        today = now.astimezone(ZoneInfo(channel.timezone)).date().isoformat()
        topic = str(candidate.get("topic") or "").strip()
        trend = candidate.get("selected_trend")
        selection = trend.get("production_selection") if isinstance(trend, dict) else None
        if (not topic or not isinstance(selection, dict) or trend.get("title") != topic
                or selection.get("eligible") is not True or selection.get("selected") is not True
                or not channel.allowed_topics
                or not any(term.casefold() in topic.casefold() for term in channel.allowed_topics)
                or any(term.casefold() in topic.casefold() for term in channel.blocked_topics)):
            raise ValueError("Commissioning needs a channel-vetted selected topic")
        from backend.services.network.topic_source import candidate_from_analysis
        measured = candidate_from_analysis(channel, {"status": "success", "best_trend": trend})
        if measured is None or any(candidate.get(signal) != measured[signal]
                                   for signal in ("quality", "evidence", "visual")):
            raise ValueError("Commissioning needs source-backed measured scores")
        score = _score(candidate)
        if score < .55:
            raise ValueError("Commissioning topic is below the production threshold")
        existing_jobs = (await session.scalars(select(NetworkJob).where(
            NetworkJob.channel_id == channel_id))).all()
        prior = next((job for job in existing_jobs
            if job.idempotency_key.startswith(f"commission:{channel_id}:{today}:")
            and job.state != "FAILED"), None)
        if prior:
            return prior
        key = f"commission:{channel_id}:{today}:{hashlib.sha256(topic.casefold().encode()).hexdigest()[:20]}"
        same = next((job for job in existing_jobs if job.idempotency_key == key), None)
        if same:
            raise PreviouslyRejectedCommission("Topic already failed private commissioning")
        used = sum(1 for job in existing_jobs if job.state != "FAILED" and
            (job.created_at.replace(tzinfo=timezone.utc)
            if job.created_at.tzinfo is None else job.created_at).astimezone(
                ZoneInfo(channel.timezone)).date().isoformat() == today)
        if used >= min(4, channel.max_daily_posts):
            raise ValueError("Channel daily capacity exhausted")
        job = await JobStore().enqueue(session, channel_id=channel_id,
            idempotency_key=key, topic=topic,
            scheduler_decision={"score": score, "local_date": today,
                "selection_source": "audited_private_commissioning",
                "selected_trend": trend})
        try:
            await OriginalityGate().reserve(session, job_id=job.id, topic=topic,
                central_claim=candidate.get("claim"), hook=candidate.get("hook"))
        except DuplicateContentError as exc:
            await JobStore().transition(session, job.id, "FAILED", reason=str(exc))
            raise
        return job

    async def allocate(self, session: AsyncSession, *, channel_id: str,
                       candidates: list[dict], at: datetime | None = None) -> NetworkAllocation:
        channel = await session.get(NetworkChannel, channel_id)
        if channel is None:
            raise LookupError("Channel not registered")
        today = (at or datetime.now(timezone.utc)).astimezone(ZoneInfo(channel.timezone)).date().isoformat()
        prior = await session.scalar(select(NetworkAllocation).where(
            NetworkAllocation.channel_id == channel_id,
            NetworkAllocation.local_date == today))
        if prior:
            return prior
        active = channel.lifecycle_state == "ACTIVE" and not channel.paused
        checked = []
        for candidate in candidates:
            topic = str(candidate.get("topic") or "").strip()
            if not topic:
                continue
            score = _score(candidate)
            trend = candidate.get("selected_trend")
            selection = trend.get("production_selection") if isinstance(trend, dict) else None
            if (not isinstance(selection, dict) or trend.get("title") != topic
                    or selection.get("eligible") is not True
                    or selection.get("selected") is not True):
                continue
            if channel.allowed_topics and not any(t.casefold() in topic.casefold()
                                                  for t in channel.allowed_topics):
                continue
            if any(t.casefold() in topic.casefold() for t in channel.blocked_topics):
                continue
            checked.append((score, topic, candidate))
        checked.sort(key=lambda row: (-row[0], row[1]))
        strongest = checked[0][0] if checked else 0
        ceiling = 4 if strongest >= .86 else 2 if strongest >= .70 else 1 if strongest >= .55 else 0
        capacity = min(4, channel.max_daily_posts, ceiling) if active else 0
        viable = [item for item in checked if item[0] >= .55]
        jobs = []
        gate, store = OriginalityGate(), JobStore()
        for score, topic, candidate in viable:
            if len(jobs) >= capacity:
                break
            key = hashlib.sha256(topic.casefold().encode()).hexdigest()[:20]
            identity_key = f"{channel_id}:{today}:{key}"
            job = await store.enqueue(session, channel_id=channel_id,
                                      idempotency_key=identity_key, topic=topic,
                                      scheduler_decision={"score": score, "local_date": today,
                                                          "selected_trend": candidate.get("selected_trend")})
            try:
                await gate.reserve(session, job_id=job.id, topic=topic,
                                   central_claim=candidate.get("claim"),
                                   hook=candidate.get("hook"))
            except DuplicateContentError as exc:
                # Failed candidates stay as an audit trail and can never run.
                if job.state == "QUEUED":
                    await store.transition(session, job.id, "FAILED", reason=str(exc))
                continue
            jobs.append(job.id)
        allocation = NetworkAllocation(channel_id=channel_id, local_date=today,
                                       target=len(jobs), selected_job_ids=jobs,
                                       rationale={"opportunity_ceiling": ceiling,
                                                  "capacity": capacity,
                                                  "candidate_count": len(checked),
                                                  "strongest_score": strongest,
                                                  "active": active})
        session.add(allocation)
        await session.commit()
        await session.refresh(allocation)
        return allocation
