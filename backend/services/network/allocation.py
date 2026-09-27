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


class DailyAllocator:
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
