#!/usr/bin/env python3
"""Select one channel-vetted topic and persist today's allocation.

Run this child through scripts/run_bounded.py, never as an unbounded service.
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.database import async_session, init_db  # noqa: E402
from backend.models.network_channel import NetworkChannel  # noqa: E402
from backend.services.network.allocation import DailyAllocator  # noqa: E402
from backend.services.network.topic_source import candidate_from_analysis  # noqa: E402


async def select_candidate(channel):
    from backend.services.commander import Commander
    analysis = await Commander().route(agent="youtube", task="analyze_trends",
                                       command_id=f"{channel.id}:network-plan",
                                       allowed_topics=channel.allowed_topics,
                                       blocked_topics=channel.blocked_topics)
    if analysis.get("status") not in {"success", "no_production_ready_topic"}:
        raise RuntimeError("Topic selection unavailable; preserve unplanned state")
    trend = analysis.get("best_trend")
    if analysis.get("status") == "success" and isinstance(trend, dict):
        from backend.services.research.evergreen_research_service import EvergreenResearchService
        pack = await asyncio.to_thread(EvergreenResearchService().research, trend["title"])
        trend["knowledge"] = pack.to_dict()
    return candidate_from_analysis(channel, analysis)


async def run(channel_id: str):
    os.environ["JARVIS_PUBLIC_PUBLISH_ENABLED"] = "false"
    await init_db()
    async with async_session() as db:
        channel = await db.get(NetworkChannel, channel_id)
        if channel is None or channel.lifecycle_state != "ACTIVE" or channel.paused:
            raise ValueError("Channel is not active")
        if not channel.allowed_topics:
            raise ValueError("Channel needs editorial allowed_topics before planning")
        candidate = await select_candidate(channel)
        decision = await DailyAllocator().allocate(db, channel_id=channel_id,
                                                   candidates=[candidate] if candidate else [])
        print(f"channel={channel_id} date={decision.local_date} jobs={decision.target}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("channel_id")
    asyncio.run(run(parser.parse_args().channel_id))
