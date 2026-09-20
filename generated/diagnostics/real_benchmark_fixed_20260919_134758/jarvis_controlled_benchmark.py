import asyncio
import inspect
import json
import os
import sys
import time
import traceback
from pathlib import Path

# ------------------------------------------------------------
# Force C:\Users\hp\jarvis.ai to be the import root.
# This script itself lives under generated\diagnostics.
# ------------------------------------------------------------

ROOT = Path.cwd().resolve()

if not (ROOT / "backend").is_dir():
    raise SystemExit(
        f"PROJECT_ROOT_INVALID: backend directory missing under {ROOT}"
    )

root_text = str(ROOT)

if root_text not in sys.path:
    sys.path.insert(0, root_text)

os.chdir(ROOT)

TOPIC = "Why movie sound effects are often recorded separately"

print("=" * 68)
print("JARVIS CONTROLLED REFERENCE-QUALITY BENCHMARK")
print("=" * 68)
print(f"[INFO] Project root: {ROOT}")
print(f"[INFO] backend exists: {(ROOT / 'backend').is_dir()}")
print(f"[INFO] Topic: {TOPIC}")
print("[INFO] Direct VideoPipeline: YES")
print("[INFO] Orchestrator: DISABLED")
print("[INFO] Publisher: DISABLED")
print("[INFO] YouTube upload: DISABLED")
print()

started = time.monotonic()

try:
    from backend.services.pipelines.video_pipeline import VideoPipeline

    print("[PASS] backend package import.")
    print("[PASS] Real VideoPipeline imported.")

    pipeline = VideoPipeline()

    print("[PASS] VideoPipeline constructed.")

    signature = inspect.signature(
        pipeline.run
    )

    parameters = list(
        signature.parameters.values()
    )

    if not parameters:
        raise RuntimeError(
            "VideoPipeline.run() exposes no input parameter."
        )

    parameter = parameters[0]

    print(
        f"[INFO] run() parameter: {parameter.name}"
    )

    print(
        f"[INFO] run() annotation: {parameter.annotation}"
    )

    trend = {
        "topic": TOPIC,
        "title": TOPIC,
        "query": TOPIC,
        "source": "controlled_reference_benchmark",
        "format": "movie_facts",
        "content_format": "movie_facts",
        "category": "movie_facts",
    }

    print()
    print("=" * 68)
    print("STARTING REAL PIPELINE")
    print("=" * 68)
    print()

    output = asyncio.run(
        pipeline.run(trend)
    )

    elapsed = time.monotonic() - started

    print()
    print("=" * 68)
    print("REAL PIPELINE COMPLETED")
    print("=" * 68)

    print(
        f"[RESULT] ElapsedSeconds={elapsed:.2f}"
    )

    print(
        f"[RESULT] ReturnType={type(output).__name__}"
    )

    if hasattr(output, "model_dump"):
        value = output.model_dump()

    elif hasattr(output, "dict"):
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

    print()
    print("[PASS] Pipeline returned successfully.")
    print("[PASS] No orchestrator used.")
    print("[PASS] No publisher used.")
    print("[PASS] No upload requested.")

    raise SystemExit(0)

except SystemExit:
    raise

except Exception as exc:
    elapsed = time.monotonic() - started

    print()
    print("=" * 68)
    print("REAL PIPELINE STOPPED")
    print("=" * 68)

    print(
        f"[RESULT] ElapsedSeconds={elapsed:.2f}"
    )

    print(
        f"[RESULT] Type={type(exc).__name__}"
    )

    print(
        f"[RESULT] Reason={exc}"
    )

    print()
    print("===== DIAGNOSTIC TRACEBACK =====")

    print(
        "".join(
            traceback.format_exception(
                type(exc),
                exc,
                exc.__traceback__,
            )
        )
    )

    print("[PASS] No orchestrator used.")
    print("[PASS] No publisher used.")
    print("[PASS] No upload requested.")

    raise SystemExit(2)
