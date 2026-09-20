from __future__ import annotations

import asyncio
import inspect
import json
import sys
import time
import traceback
import uuid

from pathlib import Path


ROOT = Path.cwd()

STAMP = sys.argv[1]

RESULT = (
    ROOT
    / "generated"
    / "diagnostics"
    / f"block5_benchmark_{STAMP}"
    / "result.json"
)

TOPIC = (
    "Why movie sound effects are often "
    "recorded separately"
)

CONTENT_ID = (
    "benchmark_"
    + uuid.uuid4().hex[:12]
)

state = {
    "success": False,
    "topic": TOPIC,
    "content_id": CONTENT_ID,
    "pipeline_class": None,
    "pipeline_module": None,
    "trend_class": None,
    "trend_module": None,
    "output": None,
    "elapsed_seconds": None,
}


def save():
    RESULT.write_text(
        json.dumps(
            state,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )


def info(message):
    print(
        f"[INFO] {message}",
        flush=True,
    )


def passed(message):
    print(
        f"[PASS] {message}",
        flush=True,
    )


def locate_class(
    class_name,
    module_candidates,
):
    import importlib

    for module_name in module_candidates:

        try:
            module = importlib.import_module(
                module_name
            )
        except Exception:
            continue

        obj = getattr(
            module,
            class_name,
            None,
        )

        if inspect.isclass(obj):
            return (
                module_name,
                obj,
            )

    return (
        None,
        None,
    )


async def main():

    started = time.monotonic()

    sys.path.insert(
        0,
        str(ROOT),
    )

    info(
        f"Topic: {TOPIC}"
    )

    info(
        f"Content ID: {CONTENT_ID}"
    )

    # ----------------------------------------
    # LOCATE REAL PIPELINE
    # ----------------------------------------

    pipeline_module, VideoPipeline = (
        locate_class(
            "VideoPipeline",
            (
                "backend.services.pipelines.video_pipeline",
                "backend.services.video_pipeline",
            ),
        )
    )

    if VideoPipeline is None:
        raise RuntimeError(
            "Could not locate VideoPipeline."
        )

    state[
        "pipeline_class"
    ] = VideoPipeline.__name__

    state[
        "pipeline_module"
    ] = pipeline_module

    passed(
        "Real VideoPipeline located."
    )

    # ----------------------------------------
    # LOCATE TREND MODEL
    # ----------------------------------------

    trend_candidates = (
        (
            "backend.models.trend",
            "Trend",
        ),
        (
            "backend.models.trends",
            "Trend",
        ),
        (
            "backend.schemas.trend",
            "Trend",
        ),
        (
            "backend.services.trend_service",
            "Trend",
        ),
        (
            pipeline_module,
            "Trend",
        ),
    )

    Trend = None
    trend_module = None

    import importlib

    for module_name, class_name in trend_candidates:

        try:

            module = importlib.import_module(
                module_name
            )

            candidate = getattr(
                module,
                class_name,
                None,
            )

            if inspect.isclass(
                candidate
            ):

                Trend = candidate
                trend_module = module_name
                break

        except Exception:
            continue

    # If Trend is imported into video_pipeline,
    # inspect the run() annotation before failing.
    if Trend is None:

        run_method = getattr(
            VideoPipeline,
            "run",
            None,
        )

        if run_method is not None:

            try:

                signature = inspect.signature(
                    run_method
                )

                parameters = list(
                    signature.parameters.values()
                )

                for parameter in parameters:

                    if parameter.name == "self":
                        continue

                    annotation = (
                        parameter.annotation
                    )

                    if (
                        annotation
                        is not inspect.Parameter.empty
                        and inspect.isclass(
                            annotation
                        )
                    ):

                        Trend = annotation
                        trend_module = (
                            annotation.__module__
                        )
                        break

            except Exception:
                pass

    if Trend is None:
        raise RuntimeError(
            "Could not locate Trend model."
        )

    state[
        "trend_class"
    ] = Trend.__name__

    state[
        "trend_module"
    ] = trend_module

    passed(
        f"Trend model located: "
        f"{trend_module}.{Trend.__name__}"
    )

    # ----------------------------------------
    # CONSTRUCT TREND ADAPTIVELY
    # ----------------------------------------

    signature = inspect.signature(
        Trend
    )

    kwargs = {}

    values = {
        "id": CONTENT_ID,
        "trend_id": CONTENT_ID,
        "content_id": CONTENT_ID,
        "topic": TOPIC,
        "title": TOPIC,
        "name": TOPIC,
        "query": TOPIC,
        "description": TOPIC,
        "summary": TOPIC,
        "source": "controlled_benchmark",
        "platform": "youtube",
        "format": "movie_facts",
        "content_format": "movie_facts",
        "category": "movie_facts",
        "score": 100,
        "trend_score": 100,
        "potential_score": 100,
    }

    unresolved_required = []

    for name, parameter in (
        signature.parameters.items()
    ):

        if name in values:
            kwargs[
                name
            ] = values[
                name
            ]
            continue

        if (
            parameter.default
            is not inspect.Parameter.empty
        ):
            continue

        annotation = (
            parameter.annotation
        )

        # Safe generic values only for obvious
        # primitive required constructor fields.
        if annotation is str:
            kwargs[name] = TOPIC

        elif annotation is int:
            kwargs[name] = 100

        elif annotation is float:
            kwargs[name] = 100.0

        elif annotation is bool:
            kwargs[name] = True

        else:
            unresolved_required.append(
                name
            )

    if unresolved_required:

        raise RuntimeError(
            "Trend has unresolved required fields: "
            + ", ".join(
                unresolved_required
            )
        )

    trend = Trend(
        **kwargs
    )

    passed(
        "Controlled benchmark Trend constructed."
    )

    # ----------------------------------------
    # CONSTRUCT PIPELINE
    # ----------------------------------------

    try:
        pipeline = VideoPipeline()
    except TypeError as exc:

        raise RuntimeError(
            "VideoPipeline no longer supports "
            "zero-argument construction: "
            + str(exc)
        ) from exc

    passed(
        "VideoPipeline constructed."
    )

    run_method = getattr(
        pipeline,
        "run",
        None,
    )

    if run_method is None:
        raise RuntimeError(
            "VideoPipeline.run not found."
        )

    # ----------------------------------------
    # REAL PIPELINE RUN
    # ----------------------------------------

    info(
        "Starting real pipeline benchmark."
    )

    info(
        "No orchestrator or publisher is used."
    )

    result = run_method(
        trend
    )

    if inspect.isawaitable(
        result
    ):
        result = await result

    elapsed = (
        time.monotonic()
        - started
    )

    state[
        "elapsed_seconds"
    ] = round(
        elapsed,
        2,
    )

    # ----------------------------------------
    # EXTRACT OUTPUT PATH
    # ----------------------------------------

    output_candidates = []

    if isinstance(
        result,
        (str, Path),
    ):
        output_candidates.append(
            str(result)
        )

    if isinstance(
        result,
        dict,
    ):

        for key in (
            "output_path",
            "video_path",
            "path",
            "render_path",
            "file_path",
            "output",
        ):

            value = result.get(
                key
            )

            if isinstance(
                value,
                (str, Path),
            ):
                output_candidates.append(
                    str(value)
                )

    else:

        for attr in (
            "output_path",
            "video_path",
            "path",
            "render_path",
            "file_path",
            "output",
        ):

            value = getattr(
                result,
                attr,
                None,
            )

            if isinstance(
                value,
                (str, Path),
            ):
                output_candidates.append(
                    str(value)
                )

    existing_outputs = []

    for candidate in output_candidates:

        path = Path(
            candidate
        )

        if not path.is_absolute():
            path = ROOT / path

        if (
            path.exists()
            and path.is_file()
        ):

            existing_outputs.append(
                path.resolve()
            )

    # Fallback: look for newly touched MP4s
    # matching the benchmark time window.
    if not existing_outputs:

        video_dir = (
            ROOT
            / "generated"
            / "videos"
        )

        if video_dir.exists():

            cutoff = (
                time.time()
                - elapsed
                - 15
            )

            fresh = [
                p
                for p in video_dir.glob(
                    "*.mp4"
                )
                if p.stat().st_mtime
                >= cutoff
            ]

            fresh.sort(
                key=lambda p:
                p.stat().st_mtime,
                reverse=True,
            )

            if fresh:
                existing_outputs.append(
                    fresh[0].resolve()
                )

    if existing_outputs:

        output = existing_outputs[0]

        state[
            "output"
        ] = str(
            output
        )

        state[
            "output_bytes"
        ] = output.stat().st_size

        passed(
            "Real MP4 produced."
        )

        print(
            f"[RESULT] MP4={output}",
            flush=True,
        )

        print(
            f"[RESULT] SIZE_BYTES="
            f"{output.stat().st_size}",
            flush=True,
        )

    else:

        info(
            "Pipeline returned without a detected "
            "MP4 path."
        )

        state[
            "raw_result"
        ] = repr(
            result
        )

    state[
        "success"
    ] = True

    save()

    print()
    print("=" * 60)
    print("BLOCK 5 BENCHMARK COMPLETED")
    print("=" * 60)

    print(
        f"[RESULT] ELAPSED_SECONDS="
        f"{state['elapsed_seconds']}",
        flush=True,
    )


try:

    asyncio.run(
        main()
    )

except BaseException as exc:

    state[
        "success"
    ] = False

    state[
        "exception_type"
    ] = type(
        exc
    ).__name__

    state[
        "exception"
    ] = str(
        exc
    )

    state[
        "traceback"
    ] = traceback.format_exc()

    save()

    print()
    print("=" * 60)
    print("BLOCK 5 BENCHMARK STOPPED")
    print("=" * 60)

    print(
        f"[RESULT] TYPE="
        f"{type(exc).__name__}",
        flush=True,
    )

    print(
        f"[RESULT] REASON="
        f"{str(exc)}",
        flush=True,
    )

    # Keep full traceback in result.json.
    # Concise terminal output is intentional.
    sys.exit(
        1
    )
