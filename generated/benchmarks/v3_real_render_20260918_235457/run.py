import asyncio
import json
import sys
import time
import traceback
from pathlib import Path
from uuid import uuid4

ROOT = Path.cwd()
OUT = Path(sys.argv[1]).resolve()
RESULT = Path(sys.argv[2]).resolve()

sys.path.insert(0, str(ROOT))

from backend.services.pipelines.video_pipeline import VideoPipeline


def clean(value):

    if value is None:
        return None

    if isinstance(value, (str, int, float, bool)):
        return value

    if isinstance(value, Path):
        return str(value)

    if isinstance(value, dict):
        return {
            str(k): clean(v)
            for k, v in value.items()
        }

    if isinstance(value, (list, tuple, set)):
        return [clean(v) for v in value]

    if hasattr(value, "model_dump"):
        try:
            return clean(value.model_dump())
        except Exception:
            pass

    if hasattr(value, "__dict__"):
        try:
            return clean(vars(value))
        except Exception:
            pass

    return str(value)


def snapshot_mp4s():

    root = ROOT / "generated"

    if not root.exists():
        return {}

    return {
        str(path.resolve()): path.stat().st_mtime
        for path in root.rglob("*.mp4")
    }


def find_new_mp4(before):

    root = ROOT / "generated"

    if not root.exists():
        return None

    candidates = []

    for path in root.rglob("*.mp4"):

        key = str(path.resolve())
        now = path.stat().st_mtime
        old = before.get(key)

        if old is None or now > old + 0.001:
            candidates.append(path)

    if not candidates:
        return None

    return max(
        candidates,
        key=lambda p: p.stat().st_mtime,
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
            "reason": "Controlled local quality benchmark.",
            "rejection_reasons": [],
        },
    }

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

    print(
        "[INFO] Starting VideoPipeline.run(trend).",
        flush=True,
    )

    print(
        "[INFO] No ProductionOrchestrator.",
        flush=True,
    )

    print(
        "[INFO] No YouTube publisher.",
        flush=True,
    )

    before = snapshot_mp4s()
    started = time.time()

    try:

        pipeline = VideoPipeline()

        result = await pipeline.run(
            trend
        )

        video = find_new_mp4(
            before
        )

        if video is None:

            payload = {
                "success": False,
                "topic": topic,
                "content_id": content_id,
                "elapsed_seconds": round(
                    time.time() - started,
                    2,
                ),
                "exception_type": "MissingRenderedVideo",
                "exception": (
                    "Pipeline returned successfully "
                    "but no new MP4 was detected."
                ),
                "pipeline_result": clean(result),
            }

        else:

            payload = {
                "success": True,
                "topic": topic,
                "content_id": content_id,
                "elapsed_seconds": round(
                    time.time() - started,
                    2,
                ),
                "video_path": str(
                    video.resolve()
                ),
                "video_bytes": (
                    video.stat().st_size
                ),
                "pipeline_result": clean(
                    result
                ),
            }

    except Exception as exc:

        payload = {
            "success": False,
            "topic": topic,
            "content_id": content_id,
            "elapsed_seconds": round(
                time.time() - started,
                2,
            ),
            "exception_type": (
                type(exc).__name__
            ),
            "exception": str(exc),
            "traceback": traceback.format_exc(),
        }

    RESULT.write_text(
        json.dumps(
            payload,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    if payload["success"]:

        print()
        print(
            "=============================================="
        )
        print(
            " BREAKTHROUGH - REAL MP4 PRODUCED"
        )
        print(
            "=============================================="
        )

        print(
            "[PASS] MP4:",
            payload["video_path"],
        )

        print(
            "[PASS] Size:",
            payload["video_bytes"],
            "bytes",
        )

        print(
            "[PASS] Elapsed:",
            payload["elapsed_seconds"],
            "seconds",
        )

    else:

        print()
        print(
            "=============================================="
        )
        print(
            " PIPELINE STOPPED"
        )
        print(
            "=============================================="
        )

        print(
            "[INFO] Type:",
            payload.get(
                "exception_type",
                "Unknown",
            ),
        )

        print(
            "[INFO] Reason:",
            payload.get(
                "exception",
                "Unknown failure",
            ),
        )


asyncio.run(main())
