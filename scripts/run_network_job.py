#!/usr/bin/env python3
"""Run one persisted job. Invoke via scripts/run_bounded.py (hard deadline).

Example: python scripts/run_bounded.py --stage network-job --timeout 7200 \
 --heartbeat 20 --log generated/logs/network-job.log -- \
 .venv/bin/python scripts/run_network_job.py JOB_ID
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.database import async_session, init_db  # noqa: E402
from backend.services.network.production_bridge import ProductionBridge  # noqa: E402


async def run(job_id: str) -> None:
    # Fail closed even if an inherited machine environment enabled release.
    os.environ["JARVIS_PUBLIC_PUBLISH_ENABLED"] = "false"
    await init_db()
    result = await ProductionBridge(async_session).run(job_id, worker_id=f"pid:{os.getpid()}")
    print(f"network_job={job_id} status={result.get('status')}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("job_id")
    args = parser.parse_args()
    asyncio.run(run(args.job_id))
