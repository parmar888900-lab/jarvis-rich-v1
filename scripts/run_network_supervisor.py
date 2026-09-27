#!/usr/bin/env python3
"""Continuous, restartable Network V1 worker; public publishing forced OFF."""

import argparse
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.database import async_session, init_db  # noqa: E402
from backend.services.network.supervisor import NetworkSupervisor  # noqa: E402


async def main(once: bool, interval: int) -> None:
    os.environ["JARVIS_PUBLIC_PUBLISH_ENABLED"] = "false"
    await init_db()
    supervisor = NetworkSupervisor(async_session)
    while True:
        try:
            print(await supervisor.tick(), flush=True)
        except Exception as exc:
            print(f"supervisor_error={type(exc).__name__}", file=sys.stderr, flush=True)
        if once:
            return
        await asyncio.sleep(interval)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--interval", type=int, default=60)
    args = parser.parse_args()
    if not 10 <= args.interval <= 3600:
        parser.error("interval must be 10 to 3600 seconds")
    asyncio.run(main(args.once, args.interval))
