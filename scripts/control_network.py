#!/usr/bin/env python3
"""Pause/resume local production or an editorial channel without publication."""

import argparse
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.database import async_session, init_db  # noqa: E402
from backend.services.network.controls import (  # noqa: E402
    GLOBAL_ACTIONS, CHANNEL_ACTIONS, apply_control,
)


async def main(action: str, channel_id: str | None):
    os.environ["JARVIS_PUBLIC_PUBLISH_ENABLED"] = "false"
    await init_db()
    async with async_session() as db:
        return await apply_control(db, action, channel_id=channel_id, confirmed=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=[*GLOBAL_ACTIONS, *CHANNEL_ACTIONS])
    parser.add_argument("--channel-id")
    args = parser.parse_args()
    print(asyncio.run(main(args.action, args.channel_id)))
