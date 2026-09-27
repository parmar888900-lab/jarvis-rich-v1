#!/usr/bin/env python3
"""Select one channel-vetted topic and persist today's allocation.

Run this child through scripts/run_bounded.py, never as an unbounded service.
"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.database import async_session, init_db  # noqa: E402
from backend.models.network_channel import NetworkChannel  # noqa: E402
from backend.services.network.allocation import DailyAllocator  # noqa: E402
from backend.services.network.topic_source import candidate_from_analysis  # noqa: E402


async def select_candidates(channel, *, route=None, research=None, limit=4):
    """Research a bounded channel-specific shortlist and keep only measured opportunities."""
    if route is None:
        from backend.services.commander import Commander
        route = Commander().route
    analysis = await route(agent="youtube", task="analyze_trends",
                           command_id=f"{channel.id}:network-plan",
                           parameters={"allowed_topics": channel.allowed_topics,
                                       "blocked_topics": channel.blocked_topics,
                                       "candidate_limit": limit})
    if analysis.get("status") not in {"success", "no_production_ready_topic"}:
        raise RuntimeError("Topic selection unavailable; preserve unplanned state")
    if analysis.get("status") != "success":
        return []
    options = analysis.get("candidate_options") or [analysis.get("best_trend")]
    if not isinstance(options, list):
        raise RuntimeError("Topic selector returned malformed candidate options")
    if research is None:
        from backend.services.research.evergreen_research_service import EvergreenResearchService
        research = EvergreenResearchService().research
    viable = []
    seen = set()
    for original in options[:limit]:
        if not isinstance(original, dict) or not original.get("title"):
            continue
        topic = str(original["title"])
        if topic.casefold() in seen:
            continue
        seen.add(topic.casefold())
        trend = {**original, "production_selection": {
            **original.get("production_selection", {}), "selected": True}}
        selection = trend["production_selection"]
        if selection.get("eligible") is not True:
            continue
        # A catalog visual/quality estimate below the gate cannot be rescued
        # by research; save provider calls for plausible alternatives.
        try:
            quality = float(selection["production_score"]) / 100
            visual = float(selection["visual_supply"]) / 100
        except (ValueError, TypeError, KeyError):
            continue
        if min(quality, visual) < .55:
            print(json.dumps({"topic": topic, "quality": quality, "visual": visual,
                              "threshold": .55, "reason": "catalog_score_below_threshold"}), flush=True)
            continue
        pack = await asyncio.to_thread(research, topic)
        trend["knowledge"] = pack.to_dict()
        candidate = candidate_from_analysis(channel, {"status": "success", "best_trend": trend})
        diagnostic = {"topic": topic, "production_score": selection["production_score"],
                      "quality": candidate["quality"] if candidate else quality,
                      "research_confidence": pack.score, "evidence": candidate["evidence"] if candidate else None,
                      "visual_supply": selection["visual_supply"], "visual": visual,
                      "source_count": len(pack.sources), "originality": "pending_reservation",
                      "threshold": .55}
        if candidate is None:
            diagnostic["reason"] = "missing_source_backed_measurement_or_editorial_rejection"
        else:
            diagnostic["weakest"] = min(candidate[key] for key in
                                        ("quality", "evidence", "visual", "originality"))
            diagnostic["reason"] = ("eligible_for_originality_reservation" if diagnostic["weakest"] >= .55
                                    else "measured_score_below_threshold")
        print(json.dumps(diagnostic, sort_keys=True), flush=True)
        if candidate is not None and diagnostic["weakest"] >= .55:
            viable.append(candidate)
    return viable


async def select_candidate(channel, *, route=None, research=None):
    candidates = await select_candidates(channel, route=route, research=research)
    return candidates[0] if candidates else None


async def run(channel_id: str):
    os.environ["JARVIS_PUBLIC_PUBLISH_ENABLED"] = "false"
    await init_db()
    async with async_session() as db:
        channel = await db.get(NetworkChannel, channel_id)
        if channel is None or channel.lifecycle_state != "ACTIVE" or channel.paused:
            raise ValueError("Channel is not active")
        if not channel.allowed_topics:
            raise ValueError("Channel needs editorial allowed_topics before planning")
        candidates = await select_candidates(channel)
        decision = await DailyAllocator().allocate(db, channel_id=channel_id,
                                                   candidates=candidates)
        print(f"channel={channel_id} date={decision.local_date} jobs={decision.target}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("channel_id")
    asyncio.run(run(parser.parse_args().channel_id))
