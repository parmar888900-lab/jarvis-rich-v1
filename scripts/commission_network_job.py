#!/usr/bin/env python3
"""One audited private QA job after a sealed zero allocation; never uploads.

Run via scripts/run_bounded.py. Repeating on the same local day is idempotent.
"""
import argparse
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.database import async_session, init_db
from backend.models.network_channel import NetworkChannel
from backend.services.network.allocation import DailyAllocator
from scripts.plan_network_day import select_candidate


async def run(channel_id: str):
    os.environ["JARVIS_PUBLIC_PUBLISH_ENABLED"] = "false"
    await init_db()
    async with async_session() as db:
        channel = await db.get(NetworkChannel, channel_id)
        if channel is None or channel.lifecycle_state != "ACTIVE" or channel.paused:
            raise ValueError("Channel is not active")
        candidate = await select_candidate(channel)
        if candidate is None:
            print("No channel-vetted source-backed opportunity; no job created", flush=True)
            return
        job = await DailyAllocator().commission_one(db, channel_id=channel_id,
                                                    candidate=candidate)
        print(f"private_qa_job={job.id} state={job.state}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("channel_id")
    asyncio.run(run(parser.parse_args().channel_id))
