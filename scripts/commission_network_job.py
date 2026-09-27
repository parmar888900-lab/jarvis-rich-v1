#!/usr/bin/env python3
"""One audited private QA job after a sealed zero allocation; never uploads.

Run via scripts/run_bounded.py. Repeating on the same local day is idempotent.
"""
import argparse
import asyncio
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.database import async_session, init_db
from backend.models.network_channel import NetworkChannel
from backend.models.network_job import NetworkJob
from backend.services.network.allocation import DailyAllocator, PreviouslyRejectedCommission
from backend.services.network.originality import DuplicateContentError
from scripts.plan_network_day import select_candidates
from sqlalchemy import select


async def run(channel_id: str):
    os.environ["JARVIS_PUBLIC_PUBLISH_ENABLED"] = "false"
    await init_db()
    async with async_session() as db:
        channel = await db.get(NetworkChannel, channel_id)
        if channel is None or channel.lifecycle_state != "ACTIVE" or channel.paused:
            raise ValueError("Channel is not active")
        local_date = datetime.now(timezone.utc).astimezone(ZoneInfo(channel.timezone)).date().isoformat()
        existing = (await db.scalars(select(NetworkJob).where(
            NetworkJob.channel_id == channel_id))).all()
        prior = next((job for job in existing if
            job.idempotency_key.startswith(f"commission:{channel_id}:{local_date}:")
            and job.state != "FAILED"), None)
        if prior:
            print(f"private_qa_job={prior.id} state={prior.state} reason=already_commissioned", flush=True)
            return
        candidates = await select_candidates(channel)
        for candidate in candidates:
            try:
                job = await DailyAllocator().commission_one(db, channel_id=channel_id,
                                                            candidate=candidate)
            except DuplicateContentError as exc:
                print(f"topic={candidate['topic']} reason=network_duplicate conflict_job={exc.conflicting_job_id}",
                      flush=True)
                continue
            except PreviouslyRejectedCommission:
                print(f"topic={candidate['topic']} reason=previously_rejected_commission", flush=True)
                continue
            print(f"private_qa_job={job.id} state={job.state}", flush=True)
            return
        print("No channel-vetted source-backed original topic cleared the .55 gate; no job created",
              flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("channel_id")
    asyncio.run(run(parser.parse_args().channel_id))
