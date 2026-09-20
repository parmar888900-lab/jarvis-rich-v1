import asyncio
import inspect
import json
import sys
import time
import traceback
from pathlib import Path

TOPIC = "Why movie sound effects are often recorded separately"

print("=" * 64)
print("JARVIS REAL MASTER-VISUAL BENCHMARK")
print("DIRECT PIPELINE / NO ORCHESTRATOR / NO PUBLISHER / NO UPLOAD")
print("=" * 64)
print()
print(f"[INFO] Topic: {TOPIC}")
print("[INFO] Upload: DISABLED")
print("[INFO] Orchestrator: DISABLED")
print("[INFO] Publisher: DISABLED")
print()

started = time.monotonic()

try:
    from backend.services.pipelines.video_pipeline import VideoPipeline

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
        f"[INFO] run() input parameter: {parameter.name}"
    )

    print(
        f"[INFO] run() annotation: {parameter.annotation}"
    )

    trend = {
        "topic": TOPIC,
        "title": TOPIC,
        "query": TOPIC,
        "source": "controlled_benchmark",
        "format": "movie_facts",
        "content_format": "movie_facts",
        "category": "movie_facts",
    }

    print("[PASS] Using plain dict benchmark input.")
    print()
    print("===== STARTING REAL PIPELINE =====")
    print()

    result = asyncio.run(
        pipeline.run(trend)
    )

    elapsed = (
        time.monotonic()
        - started
    )

    print()
    print("=" * 64)
    print("PIPELINE RETURNED SUCCESSFULLY")
    print("=" * 64)

    print(
        f"[RESULT] ElapsedSeconds={elapsed:.2f}"
    )

    print(
        f"[RESULT] ReturnType={type(result).__name__}"
    )

    try:
        if hasattr(
            result,
            "model_dump"
        ):
            serializable = (
                result.model_dump()
            )

        elif hasattr(
            result,
            "dict"
        ):
            serializable = (
                result.dict()
            )

        elif isinstance(
            result,
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
            serializable = result

        else:
            serializable = {
                "repr": repr(result)
            }

        print(
            "[RESULT_JSON] "
            + json.dumps(
                serializable,
                ensure_ascii=False,
                default=str,
            )
        )

    except Exception as serialization_error:

        print(
            "[RESULT_REPR] "
            + repr(result)
        )

        print(
            "[INFO] Result serialization issue: "
            + str(serialization_error)
        )

    print()
    print("[PASS] Real pipeline completed.")
    print("[PASS] No orchestrator used.")
    print("[PASS] No publisher used.")
    print("[PASS] No YouTube upload requested.")

    sys.exit(0)

except Exception as exc:

    elapsed = (
        time.monotonic()
        - started
    )

    print()
    print("=" * 64)
    print("PIPELINE STOPPED")
    print("=" * 64)

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
    print("[INFO] Full diagnostic traceback follows.")
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
    print("[PASS] No YouTube upload requested.")

    sys.exit(2)
