#!/usr/bin/env python3
"""Bounded local capability, safety and persisted-network check."""

import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("DEBUG", "false")

from backend.database import async_session, init_db  # noqa: E402
from backend.services.network.status import network_snapshot  # noqa: E402


async def main() -> dict:
    await init_db()
    async with async_session() as db:
        snapshot = await network_snapshot(db, storage_path=Path.cwd())
    return {"public_publishing_enabled": snapshot["public_publishing_enabled"],
            "network_publishing_enabled": snapshot["controls"]["publishing_enabled"],
            "production_enabled": snapshot["controls"]["production_enabled"],
            "channels": len(snapshot["channels"]), "job_counts": snapshot["job_counts"],
            "open_human_actions": len(snapshot["human_actions"]),
            "missing_production_dependencies": snapshot["runtime_capabilities"]["missing_required"],
            "disk_free_bytes": snapshot["system"]["disk_free_bytes"],
            "supervisor": snapshot["services"]["supervisor"],
            "voice": snapshot["services"]["voice"]}


if __name__ == "__main__":
    print(json.dumps(asyncio.run(main()), indent=2))
