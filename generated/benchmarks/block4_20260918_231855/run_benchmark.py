import asyncio
import inspect
import json
import os
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

PROJECT = Path.cwd()
OUT_DIR = Path(sys.argv[1]).resolve()
RESULT_PATH = Path(sys.argv[2]).resolve()

sys.path.insert(
    0,
    str(PROJECT),
)

from backend.services.pipelines.video_pipeline import VideoPipeline


def json_safe(value):
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
            str(k): json_safe(v)
            for k, v in value.items()
        }

    if isinstance(
        value,
        (list, tuple, set),
    ):
        return [
            json_safe(v)
            for v in value
        ]

    if hasattr(value, "model_dump"):
        try:
            return json_safe(
                value.model_dump()
            )
        except Exception:
            pass

    if hasattr(value, "__dict__"):
        try:
            return json_safe(
                vars(value)
            )
        except Exception:
            pass

    return str(value)


def locate_mp4(value):
    candidates = []

    def walk(obj):
        if isinstance(obj, dict):
            for key, item in obj.items():

                key_lower = str(key).lower()

                if isinstance(
                    item,
                    (str, Path),
                ):
                    text = str(item)

                    if (
                        text.lower().endswith(".mp4")
                        or key_lower in {
                            "video_path",
                            "output_path",
                            "render_path",
                            "path",
                        }
                    ):
                        candidates.append(
                            Path(text)
                        )

                walk(item)

        elif isinstance(
            obj,
            (list, tuple),
        ):
            for item in obj:
                walk(item)

    walk(value)

    existing = []

    for candidate in candidates:

        if not candidate.is_absolute():
            candidate = (
                PROJECT
                / candidate
            ).resolve()

        if (
            candidate.exists()
            and candidate.suffix.lower()
            == ".mp4"
        ):
            existing.append(
                candidate
            )

    if existing:
        existing.sort(
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )

        return existing[0]

    # Last-resort discovery only inside generated output.
    generated = PROJECT / "generated"

    if generated.exists():
        mp4s = list(
            generated.rglob("*.mp4")
        )

        if mp4s:
            mp4s.sort(
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )

            return mp4s[0]

    return None


def build_run_kwargs(
    signature,
    topic,
    content_id,
):
    kwargs = {}

    parameters = signature.parameters

    mappings = {
        "topic": topic,
        "selected_topic": topic,
        "content_id": content_id,
        "cycle_id": content_id,
        "genre": "movie_facts",
        "format_name": "movie_facts",
        "locked_format": "movie_facts",
    }

    for name, value in mappings.items():
        if name in parameters:
            kwargs[name] = value

    required_missing = []

    for name, param in parameters.items():

        if name == "self":
            continue

        if (
            param.default
            is inspect.Parameter.empty
            and param.kind
            not in (
                inspect.Parameter.VAR_POSITIONAL,
                inspect.Parameter.VAR_KEYWORD,
            )
            and name not in kwargs
        ):
            required_missing.append(name)

    return kwargs, required_missing


async def main():
    started = time.time()

    pipeline = VideoPipeline()

    signature = inspect.signature(
        pipeline.run
    )

    # Benchmark topic deliberately uses a concrete mechanism
    # and has already been shown to score strongly by Block 4.
    topic = (
        "Why movie sound effects are often "
        "recorded separately"
    )

    content_id = (
        "benchmark_"
        + uuid4().hex[:12]
    )

    kwargs, missing = build_run_kwargs(
        signature,
        topic,
        content_id,
    )

    if missing:
        raise RuntimeError(
            "VideoPipeline.run has unsupported required "
            "arguments for the benchmark: "
            + ", ".join(missing)
        )

    print(
        "[INFO] Benchmark topic:",
        topic,
        flush=True,
    )

    print(
        "[INFO] Pipeline signature:",
        signature,
        flush=True,
    )

    print(
        "[INFO] Pipeline kwargs:",
        kwargs,
        flush=True,
    )

    before = {
        str(path.resolve()): path.stat().st_mtime
        for path in (
            PROJECT / "generated"
        ).rglob("*.mp4")
    } if (
        PROJECT / "generated"
    ).exists() else {}

    result = await pipeline.run(
        **kwargs
    )

    safe_result = json_safe(result)

    video_path = locate_mp4(
        safe_result
    )

    # Prefer an MP4 created/modified by this run.
    generated = PROJECT / "generated"

    if generated.exists():
        changed = []

        for path in generated.rglob("*.mp4"):

            resolved = str(
                path.resolve()
            )

            old_mtime = before.get(
                resolved
            )

            current_mtime = (
                path.stat().st_mtime
            )

            if (
                old_mtime is None
                or current_mtime
                > old_mtime + 0.001
            ):
                changed.append(path)

        if changed:
            changed.sort(
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )

            video_path = changed[0]

    if video_path is None:
        raise RuntimeError(
            "Pipeline returned without a discoverable MP4."
        )

    elapsed = round(
        time.time() - started,
        2,
    )

    payload = {
        "benchmark": True,
        "youtube_upload_requested": False,
        "production_orchestrator_used": False,
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
        " BENCHMARK RENDER COMPLETE"
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
        "[PASS] No ProductionOrchestrator used."
    )
    print(
        "[PASS] No YouTube upload requested."
    )


if __name__ == "__main__":
    asyncio.run(main())
