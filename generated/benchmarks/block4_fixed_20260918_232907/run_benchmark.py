import asyncio
import json
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

ROOT = Path.cwd()
OUT_DIR = Path(sys.argv[1]).resolve()
RESULT_PATH = Path(sys.argv[2]).resolve()

sys.path.insert(0, str(ROOT))

from backend.services.pipelines.video_pipeline import VideoPipeline


def safe(value):
    if value is None:
        return None

    if isinstance(
        value,
        (str, int, float, bool),
    ):
        return value

    if isinstance(value, Path):
        return str(value)

    if isinstance(value, dict):
        return {
            str(key): safe(item)
            for key, item in value.items()
        }

    if isinstance(
        value,
        (list, tuple, set),
    ):
        return [
            safe(item)
            for item in value
        ]

    if hasattr(value, "model_dump"):
        try:
            return safe(
                value.model_dump()
            )
        except Exception:
            pass

    if hasattr(value, "__dict__"):
        try:
            return safe(
                vars(value)
            )
        except Exception:
            pass

    return str(value)


def snapshot_mp4s():
    generated = ROOT / "generated"

    if not generated.exists():
        return {}

    return {
        str(path.resolve()): path.stat().st_mtime
        for path in generated.rglob("*.mp4")
    }


def find_new_mp4(before):
    generated = ROOT / "generated"

    if not generated.exists():
        return None

    changed = []

    for path in generated.rglob("*.mp4"):

        resolved = str(
            path.resolve()
        )

        current = (
            path.stat().st_mtime
        )

        previous = before.get(
            resolved
        )

        if (
            previous is None
            or current > previous + 0.001
        ):
            changed.append(path)

    if not changed:
        return None

    changed.sort(
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )

    return changed[0]


async def main():

    started = time.time()

    topic = (
        "Why movie sound effects are often "
        "recorded separately"
    )

    content_id = (
        "benchmark_"
        + uuid4().hex[:12]
    )

    # Exact VideoPipeline.run contract:
    #     run(trend: dict) -> dict
    #
    # Keep this isolated from ProductionOrchestrator,
    # publisher and daily batch state.

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
            "reason": (
                "Controlled local quality benchmark."
            ),
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
        "[INFO] Calling VideoPipeline.run(trend).",
        flush=True,
    )

    print(
        "[INFO] ProductionOrchestrator bypassed.",
        flush=True,
    )

    print(
        "[INFO] YouTube publisher bypassed.",
        flush=True,
    )

    before = snapshot_mp4s()

    pipeline = VideoPipeline()

    try:
        result = await pipeline.run(
            trend
        )

    except Exception as exc:

        full_traceback = traceback.format_exc()

        failure = {
            "benchmark": True,
            "success": False,
            "topic": topic,
            "content_id": content_id,
            "exception_type": type(exc).__name__,
            "exception": str(exc),
            "traceback": full_traceback,
            "youtube_upload_requested": False,
            "production_orchestrator_used": False,
        }

        RESULT_PATH.write_text(
            json.dumps(
                failure,
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        print()
        print(
            "========================================================"
        )
        print(
            " PIPELINE FAILURE - FULL DIAGNOSTIC"
        )
        print(
            "========================================================"
        )
        print(
            full_traceback
        )

        # Deliberately return normally.
        # PowerShell can read the structured failure JSON
        # instead of losing the useful traceback.
        return

    video_path = find_new_mp4(
        before
    )

    safe_result = safe(
        result
    )

    if video_path is None:

        # Inspect result for an explicit MP4 path.
        possible = []

        def walk(value):
            if isinstance(value, dict):
                for item in value.values():
                    walk(item)

            elif isinstance(
                value,
                (list, tuple),
            ):
                for item in value:
                    walk(item)

            elif isinstance(
                value,
                (str, Path),
            ):
                text = str(value)

                if text.lower().endswith(".mp4"):
                    possible.append(
                        Path(text)
                    )

        walk(safe_result)

        for candidate in possible:

            if not candidate.is_absolute():
                candidate = (
                    ROOT
                    / candidate
                ).resolve()

            if candidate.exists():
                video_path = candidate
                break

    if video_path is None:

        failure = {
            "benchmark": True,
            "success": False,
            "topic": topic,
            "content_id": content_id,
            "exception_type": "MissingRenderedVideo",
            "exception": (
                "Pipeline completed but no new MP4 "
                "could be identified."
            ),
            "pipeline_result": safe_result,
            "youtube_upload_requested": False,
            "production_orchestrator_used": False,
        }

        RESULT_PATH.write_text(
            json.dumps(
                failure,
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        print(
            "[FAIL] Pipeline completed but no new MP4 "
            "was identified."
        )

        return

    elapsed = round(
        time.time() - started,
        2,
    )

    payload = {
        "benchmark": True,
        "success": True,
        "topic": topic,
        "content_id": content_id,
        "started_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "elapsed_seconds": elapsed,
        "video_path": str(
            video_path.resolve()
        ),
        "video_bytes": (
            video_path.stat().st_size
        ),
        "youtube_upload_requested": False,
        "production_orchestrator_used": False,
        "pipeline_result": safe_result,
    }

    RESULT_PATH.write_text(
        json.dumps(
            payload,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print()
    print(
        "========================================================"
    )
    print(
        " REAL BENCHMARK RENDER COMPLETE"
    )
    print(
        "========================================================"
    )

    print(
        "[PASS] MP4:",
        video_path.resolve(),
    )

    print(
        "[PASS] Size:",
        video_path.stat().st_size,
        "bytes",
    )

    print(
        "[PASS] Elapsed:",
        elapsed,
        "seconds",
    )

    print(
        "[PASS] No ProductionOrchestrator."
    )

    print(
        "[PASS] No YouTube upload."
    )


if __name__ == "__main__":
    asyncio.run(main())
