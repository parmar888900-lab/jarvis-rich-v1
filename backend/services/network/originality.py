"""Conservative persistent near-duplicate gate across every channel."""

from __future__ import annotations

import re
from difflib import SequenceMatcher

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.network_identity import NetworkContentIdentity
from backend.models.network_job import NetworkJob


def _tokens(value: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", value.casefold()))


def similarity(a: str, b: str) -> float:
    left, right = _tokens(a), _tokens(b)
    if not left or not right:
        return 0.0
    jaccard = len(left & right) / len(left | right)
    # Sequence ratio preserves differences in narrative ordering when bags
    # of words match. Use the more conservative (larger) similarity.
    return max(jaccard, SequenceMatcher(None, " ".join(sorted(left)),
                                        " ".join(sorted(right))).ratio())


class DuplicateContentError(ValueError):
    def __init__(self, job_id: str, signal: str):
        self.conflicting_job_id = job_id
        self.signal = signal
        super().__init__(f"Network duplicate {signal} conflicts with job {job_id}")


class OriginalityGate:
    def _conflict(self, candidate: dict, previous: NetworkContentIdentity) -> str | None:
        for signal, threshold in (("topic", .88), ("central_claim", .82),
                                  ("hook", .85), ("script", .86),
                                  ("title", .90), ("description", .93)):
            a, b = candidate.get(signal), getattr(previous, signal)
            if a and b and similarity(a, b) >= threshold:
                return signal
        for signal in ("render_sha256", "narration_sha256"):
            if candidate.get(signal) and candidate[signal] == getattr(previous, signal):
                return signal
        for signal in ("media_fingerprints",):
            a, b = set(candidate.get(signal) or ()), set(getattr(previous, signal) or ())
            if a and b and len(a & b) / len(a | b) >= .9:
                return signal
        a, b = candidate.get("shot_sequence") or [], previous.shot_sequence or []
        if len(a) >= 3 and a == b:
            return "shot_sequence"
        return None

    async def reserve(self, session: AsyncSession, *, job_id: str,
                      topic: str, **signals) -> NetworkContentIdentity:
        if not topic.strip():
            raise ValueError("Originality reservation needs a topic")
        allowed = {column.name for column in NetworkContentIdentity.__table__.columns}
        if set(signals) - allowed:
            raise ValueError("Unknown originality signal")
        connection = await session.connection()
        if connection.dialect.name == "sqlite":
            # Reserve a write transaction before reading all identities so
            # competing processes cannot simultaneously pass near-duplicate checks.
            await connection.exec_driver_sql("BEGIN IMMEDIATE")
        existing = await session.scalar(select(NetworkContentIdentity).where(
            NetworkContentIdentity.job_id == job_id))
        if existing:
            if existing.topic != topic:
                raise ValueError("Cannot change a reserved job topic")
            return existing
        job = await session.get(NetworkJob, job_id)
        if job is None:
            raise LookupError("Job not found")
        candidate = {"topic": topic, **signals}
        rows = await session.scalars(select(NetworkContentIdentity))
        for prior in rows:
            signal = self._conflict(candidate, prior)
            if signal:
                raise DuplicateContentError(prior.job_id, signal)
        record = NetworkContentIdentity(job_id=job_id, channel_id=job.channel_id,
                                        **{k: v for k, v in candidate.items() if k in allowed})
        session.add(record)
        try:
            await session.commit()
        except IntegrityError as exc:
            await session.rollback()
            raise ValueError("Conflicting content identity reservation") from exc
        await session.refresh(record)
        return record
