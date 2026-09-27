#!/usr/bin/env python3
"""Register an editorial channel for local QA-only production.

Example: .venv/Scripts/python.exe scripts/configure_network_channel.py \
 --name SpaceDecoded --niche science --editorial "Webb engineering explained" \
 --allow-topic Webb --activate
No YouTube channel is created or authorized by this command.
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.database import async_session, init_db  # noqa: E402
from backend.services.network.channel_registry import ChannelRegistry  # noqa: E402


async def register(args, sessions=async_session):
    os.environ["JARVIS_PUBLIC_PUBLISH_ENABLED"] = "false"
    async with sessions() as db:
        channel = await ChannelRegistry().register(
            db, name=args.name, niche=args.niche, editorial_identity=args.editorial,
            allowed_topics=args.allow_topic, blocked_topics=args.block_topic,
            max_daily_posts=args.max_daily, timezone=args.timezone)
        if args.activate:
            channel = await ChannelRegistry().set_state(db, channel.id, "ACTIVE")
        return channel


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", required=True)
    parser.add_argument("--niche", required=True)
    parser.add_argument("--editorial", required=True)
    parser.add_argument("--allow-topic", action="append", required=True)
    parser.add_argument("--block-topic", action="append", default=[])
    parser.add_argument("--max-daily", type=int, default=4)
    parser.add_argument("--timezone", default="UTC")
    parser.add_argument("--activate", action="store_true")
    args = parser.parse_args()
    asyncio.run(init_db())
    created = asyncio.run(register(args))
    print(f"channel_id={created.id} lifecycle={created.lifecycle_state} public_publishing=OFF")
