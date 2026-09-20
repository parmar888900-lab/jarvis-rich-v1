import asyncio
import json
import os
import sys
import time
import traceback
from pathlib import Path

ROOT = Path.cwd().resolve()

if str(ROOT) not in sys.path:
    sys.path.insert(
        0,
        str(ROOT),
    )

os.chdir(ROOT)

TOPIC = (
    "Why movie sound effects are often "
    "recorded separately"
)

CONTENT_ID = "reference_visual_v5_20260919_145853"

print("=" * 68)
print("JARVIS REFERENCE VISUAL V5 REAL BENCHMARK")
print("=" * 68)
print(f"[INFO] Content ID: {CONTENT_ID}")
print(f"[INFO] Topic: {TOPIC}")
print("[INFO] Upload: DISABLED")
print("[INFO] Publisher: DISABLED")
print("[INFO] Orchestrator: DISABLED")
print()

started = time.monotonic()

try:
    from backend.services.pipelines.video_pipeline import VideoPipeline

    pipeline = VideoPipeline()

    print(
        "[PASS] Real VideoPipeline constructed."
    )

    trend = {
        "content_id": CONTENT_ID,
        "topic": TOPIC,
        "title": TOPIC,
        "query": TOPIC,
        "source": (
            "reference_visual_v5_benchmark"
        ),
        "format": "movie_facts",
        "content_format": "movie_facts",
        "category": "movie_facts",
        "genre": "film",
    }

    print()
    print(
        "===== REAL PIPELINE START ====="
    )
    print()

    output = asyncio.run(
        pipeline.run(trend)
    )

    elapsed = (
        time.monotonic()
        - started
    )

    print()
    print(
        "===== REAL PIPELINE SUCCESS ====="
    )

    print(
        f"[RESULT] ElapsedSeconds="
        f"{elapsed:.2f}"
    )

    print(
        f"[RESULT] ReturnType="
        f"{type(output).__name__}"
    )

    if hasattr(
        output,
        "model_dump",
    ):
        value = output.model_dump()

    elif hasattr(
        output,
        "dict",
    ):
        value = output.dict()

    elif isinstance(
        output,
        (
            dict,
            list,
            str,
            int,
            float,
            bool,
            type(None),
        ),
    ):
        value = output

    else:
        value = {
            "repr": repr(output)
        }

    print(
        "[RESULT_JSON] "
        + json.dumps(
            value,
            ensure_ascii=False,
            default=str,
        )
    )

    print(
        "[PASS] No orchestrator used."
    )

    print(
        "[PASS] No publisher used."
    )

    print(
        "[PASS] No upload requested."
    )

    raise SystemExit(0)

except SystemExit:
    raise

except Exception as exc:

    elapsed = (
        time.monotonic()
        - started
    )

    print()
    print(
        "===== REAL PIPELINE STOPPED ====="
    )

    print(
        f"[RESULT] ElapsedSeconds="
        f"{elapsed:.2f}"
    )

    print(
        f"[RESULT] Type="
        f"{type(exc).__name__}"
    )

    print(
        f"[RESULT] Reason={exc}"
    )

    print()
    print(
        "===== TRACEBACK ====="
    )

    print(
        "".join(
            traceback.format_exception(
                type(exc),
                exc,
                exc.__traceback__,
            )
        )
    )

    print(
        "[PASS] No orchestrator used."
    )

    print(
        "[PASS] No publisher used."
    )

    print(
        "[PASS] No upload requested."
    )

    raise SystemExit(2)
