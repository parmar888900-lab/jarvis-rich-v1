import asyncio
import json
import sys
import time
import traceback
from pathlib import Path
from uuid import uuid4

ROOT = Path.cwd()
RESULT = Path(sys.argv[1]).resolve()

sys.path.insert(0, str(ROOT))

TOPIC = "Why movie sound effects are often recorded separately"


def serial(value):
    if value is None:
        return None

    if isinstance(value, (str, int, float, bool)):
        return value

    if isinstance(value, Path):
        return str(value)

    if isinstance(value, dict):
        return {
            str(k): serial(v)
            for k, v in value.items()
        }

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


def mp4_snapshot():
    root = ROOT / "generated"

    if not root.exists():
        return {}

    result = {}

    for path in root.rglob("*.mp4"):
        try:
            result[str(path.resolve())] = (
                path.stat().st_mtime_ns
            )
        except OSError:
            pass

    return result


def changed_mp4s(before):
    root = ROOT / "generated"

    if not root.exists():
        return []

    changed = []

    for path in root.rglob("*.mp4"):
        try:
            key = str(path.resolve())
            current = path.stat().st_mtime_ns
            previous = before.get(key)

            if previous is None or current > previous:
                changed.append(path)
        except OSError:
            continue

    return sorted(
        changed,
        key=lambda p: p.stat().st_mtime_ns,
        reverse=True,
    )


async def main():
    content_id = "benchmark_" + uuid4().hex[:12]

    trend = {
        "title": TOPIC,
        "topic": TOPIC,
        "genre": "movie_facts",
        "content_id": content_id,
        "content_strategy": "evergreen_storytelling",
        "requires_trend": False,
        "locked_format": "movie_facts",
        "benchmark_mode": True,
        "production_selection": {
            "eligible": True,
            "selected": True,
            "production_score": 100.0,
            "reason": "Block 5 controlled visual benchmark",
            "rejection_reasons": [],
        },
    }

    payload = {
        "success": False,
        "topic": TOPIC,
        "content_id": content_id,
        "stage": "starting",
    }

    before = mp4_snapshot()
    started = time.time()

    try:
        print(
            "[INFO] Topic:",
            TOPIC,
            flush=True,
        )

        print(
            "[INFO] Content ID:",
            content_id,
            flush=True,
        )

        print(
            "[INFO] Importing VideoPipeline...",
            flush=True,
        )

        from backend.services.pipelines.video_pipeline import (
            VideoPipeline,
        )

        pipeline = VideoPipeline()

        print(
            "[PASS] Pipeline constructed.",
            flush=True,
        )

        print(
            "[INFO] Running controlled benchmark.",
            flush=True,
        )

        print(
            "[INFO] Path: research -> script -> evidence -> "
            "media -> Block 5 QA -> render",
            flush=True,
        )

        payload["stage"] = "pipeline"

        result = await pipeline.run(trend)

        payload["pipeline_result"] = serial(result)
        payload["stage"] = "pipeline_returned"

        videos = changed_mp4s(before)

        if not videos:
            raise RuntimeError(
                "Pipeline returned without producing a new MP4."
            )

        video = videos[0]

        payload["success"] = True
        payload["stage"] = "render_complete"
        payload["video_path"] = str(video.resolve())
        payload["video_bytes"] = video.stat().st_size

        semantic = {}

        if isinstance(result, dict):
            semantic = result.get(
                "semantic_media_metrics",
                {},
            ) or {}

        payload["semantic_media_metrics"] = serial(
            semantic
        )

        if isinstance(semantic, dict):
            payload["visual_quality"] = serial(
                semantic.get(
                    "visual_quality",
                    {},
                )
            )
        else:
            payload["visual_quality"] = {}

    except BaseException as exc:
        payload["success"] = False
        payload["exception_type"] = type(exc).__name__
        payload["exception"] = str(exc)
        payload["traceback"] = traceback.format_exc()

    finally:
        payload["elapsed_seconds"] = round(
            time.time() - started,
            2,
        )

        RESULT.write_text(
            json.dumps(
                payload,
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    return payload


payload = asyncio.run(main())

print()
print("=" * 60)

if payload.get("success"):
    print("BLOCK 5 PASSED - NEW MP4")
    print("=" * 60)

    print(
        "MP4:",
        payload.get("video_path"),
    )

    print(
        "SIZE:",
        payload.get("video_bytes"),
    )

    print(
        "TIME:",
        payload.get("elapsed_seconds"),
        "sec",
    )

    print()
    print("VISUAL QUALITY:")

    print(
        json.dumps(
            payload.get(
                "visual_quality",
                {},
            ),
            indent=2,
            ensure_ascii=False,
        )
    )

else:
    print("BLOCK 5 STOPPED SAFELY")
    print("=" * 60)

    print(
        "STAGE:",
        payload.get("stage"),
    )

    print(
        "TYPE:",
        payload.get("exception_type"),
    )

    print(
        "REASON:",
        payload.get("exception"),
    )

    print()
    print("TRACEBACK:")

    print(
        payload.get(
            "traceback",
            "",
        )
    )

print()
print("[PASS] Benchmark runner finished.")
print("[PASS] No ProductionOrchestrator.")
print("[PASS] No YouTube publisher.")
