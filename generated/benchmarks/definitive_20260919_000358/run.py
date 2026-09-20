import asyncio
import contextlib
import io
import json
import logging
import sys
import time
import traceback
from pathlib import Path
from uuid import uuid4

ROOT = Path.cwd()
RESULT = Path(sys.argv[1]).resolve()

sys.path.insert(0, str(ROOT))


def serial(value):
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(k): serial(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [serial(v) for v in value]
    if hasattr(value, "model_dump"):
        try:
            return serial(value.model_dump())
        except Exception:
            pass
    if hasattr(value, "__dict__"):
        try:
            return serial(vars(value))
        except Exception:
            pass
    return str(value)


def snapshot():
    root = ROOT / "generated"
    if not root.exists():
        return {}

    return {
        str(p.resolve()): p.stat().st_mtime
        for p in root.rglob("*.mp4")
    }


def changed_mp4(before):
    root = ROOT / "generated"
    if not root.exists():
        return None

    found = []

    for p in root.rglob("*.mp4"):
        key = str(p.resolve())
        stamp = p.stat().st_mtime
        old = before.get(key)

        if old is None or stamp > old + 0.001:
            found.append(p)

    if not found:
        return None

    return max(found, key=lambda p: p.stat().st_mtime)


async def execute():

    topic = "Why movie sound effects are often recorded separately"
    cid = "benchmark_" + uuid4().hex[:12]

    trend = {
        "title": topic,
        "topic": topic,
        "genre": "movie_facts",
        "content_id": cid,
        "content_strategy": "evergreen_storytelling",
        "requires_trend": False,
        "locked_format": "movie_facts",
        "benchmark_mode": True,
        "production_selection": {
            "eligible": True,
            "selected": True,
            "production_score": 100.0,
            "reason": "Controlled benchmark",
            "rejection_reasons": [],
        },
    }

    started = time.time()
    before = snapshot()

    payload = {
        "success": False,
        "topic": topic,
        "content_id": cid,
    }

    print("[INFO] Topic:", topic, flush=True)
    print("[INFO] Content ID:", cid, flush=True)

    try:
        print("[STEP] Importing VideoPipeline...", flush=True)

        from backend.services.pipelines.video_pipeline import VideoPipeline

        print("[PASS] Import complete.", flush=True)

        print("[STEP] Constructing VideoPipeline...", flush=True)

        pipeline = VideoPipeline()

        print("[PASS] Construction complete.", flush=True)

        print("[STEP] Calling pipeline.run(trend)...", flush=True)

        pipeline_result = await pipeline.run(trend)

        print("[PASS] pipeline.run returned.", flush=True)

        video = changed_mp4(before)

        payload["elapsed_seconds"] = round(
            time.time() - started,
            2,
        )

        payload["pipeline_result"] = serial(
            pipeline_result
        )

        if video is None:
            payload["exception_type"] = "MissingRenderedVideo"
            payload["exception"] = (
                "Pipeline returned but no new MP4 was detected."
            )
        else:
            payload["success"] = True
            payload["video_path"] = str(video.resolve())
            payload["video_bytes"] = video.stat().st_size

    except BaseException as exc:

        payload["elapsed_seconds"] = round(
            time.time() - started,
            2,
        )

        payload["exception_type"] = type(exc).__name__
        payload["exception"] = str(exc)
        payload["traceback"] = traceback.format_exc()

        print("", flush=True)
        print("[CAPTURED FAILURE]", flush=True)
        print("TYPE:", type(exc).__name__, flush=True)
        print("REASON:", str(exc), flush=True)
        print("", flush=True)
        print(traceback.format_exc(), flush=True)

    finally:

        try:
            RESULT.write_text(
                json.dumps(
                    payload,
                    indent=2,
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            print(
                "[PASS] result.json written:",
                RESULT,
                flush=True,
            )

        except BaseException:
            print(
                "[FATAL] Could not write result.json",
                flush=True,
            )
            print(
                traceback.format_exc(),
                flush=True,
            )

    return payload


async def main():

    try:
        return await execute()

    except BaseException as exc:

        payload = {
            "success": False,
            "exception_type": type(exc).__name__,
            "exception": str(exc),
            "traceback": traceback.format_exc(),
        }

        try:
            RESULT.write_text(
                json.dumps(
                    payload,
                    indent=2,
                ),
                encoding="utf-8",
            )
        except BaseException:
            pass

        print("[OUTER FAILURE]", flush=True)
        print(traceback.format_exc(), flush=True)

        return payload


payload = asyncio.run(main())

print("", flush=True)

if payload.get("success"):
    print("==============================================", flush=True)
    print(" REAL MP4 PRODUCED", flush=True)
    print("==============================================", flush=True)
    print(payload.get("video_path"), flush=True)
else:
    print("==============================================", flush=True)
    print(" EXACT FAILURE CAPTURED", flush=True)
    print("==============================================", flush=True)
    print("TYPE:", payload.get("exception_type"), flush=True)
    print("REASON:", payload.get("exception"), flush=True)
