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
        return [
            serial(v)
            for v in value
        ]

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

    return {
        str(path.resolve()): path.stat().st_mtime
        for path in root.rglob("*.mp4")
    }


def newest_changed_mp4(before):
    root = ROOT / "generated"

    if not root.exists():
        return None

    changed = []

    for path in root.rglob("*.mp4"):
        key = str(path.resolve())
        timestamp = path.stat().st_mtime
        previous = before.get(key)

        if previous is None or timestamp > previous + 0.001:
            changed.append(path)

    if not changed:
        return None

    return max(
        changed,
        key=lambda path: path.stat().st_mtime,
    )


async def main():

    topic = (
        "Why movie sound effects are often "
        "recorded separately"
    )

    content_id = (
        "benchmark_"
        + uuid4().hex[:12]
    )

    trend = {
        "title": topic,
        "topic": topic,
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
        "topic": topic,
        "content_id": content_id,
    }

    started = time.time()
    before = mp4_snapshot()

    try:
        print(
            "[INFO] Topic:",
            topic,
            flush=True,
        )

        print(
            "[INFO] Content ID:",
            content_id,
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
            "[INFO] Running research -> content -> media -> Block 5 QA.",
            flush=True,
        )

        result = await pipeline.run(
            trend
        )

        payload["pipeline_result"] = serial(
            result
        )

        payload["elapsed_seconds"] = round(
            time.time() - started,
            2,
        )

        video = newest_changed_mp4(
            before
        )

        if video is None:
            raise RuntimeError(
                "Pipeline returned success but no new MP4 was detected."
            )

        payload["success"] = True
        payload["video_path"] = str(
            video.resolve()
        )
        payload["video_bytes"] = (
            video.stat().st_size
        )

        semantic = result.get(
            "semantic_media_metrics",
            {},
        )

        payload["visual_quality"] = (
            semantic.get(
                "visual_quality",
                {},
            )
        )

    except BaseException as exc:

        payload["elapsed_seconds"] = round(
            time.time() - started,
            2,
        )

        payload["exception_type"] = (
            type(exc).__name__
        )

        payload["exception"] = str(
            exc
        )

        payload["traceback"] = (
            traceback.format_exc()
        )

    finally:

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
print("==============================================")

if payload.get("success"):
    print("BLOCK 5 BENCHMARK PASSED")
    print("==============================================")
    print(
        "MP4:",
        payload.get("video_path"),
    )
    print(
        "VISUAL QA:",
        json.dumps(
            payload.get(
                "visual_quality",
                {},
            ),
            indent=2,
        ),
    )
else:
    print("BLOCK 5 BENCHMARK STOPPED")
    print("==============================================")
    print(
        "TYPE:",
        payload.get("exception_type"),
    )
    print(
        "REASON:",
        payload.get("exception"),
    )
    print()
    print(
        payload.get(
            "traceback",
            "",
        )
    )
