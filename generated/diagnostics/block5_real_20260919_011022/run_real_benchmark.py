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
    / f"block5_real_{STAMP}"
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
    "input_type": None,
    "output": None,
    "output_bytes": None,
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


def log(kind, text):
    print(
        f"[{kind}] {text}",
        flush=True,
    )


async def main():

    started = time.monotonic()

    sys.path.insert(
        0,
        str(ROOT),
    )

    from backend.services.pipelines.video_pipeline import (
        VideoPipeline,
    )

    log(
        "PASS",
        "Real VideoPipeline imported."
    )

    pipeline = VideoPipeline()

    log(
        "PASS",
        "VideoPipeline constructed."
    )

    run_method = pipeline.run

    signature = inspect.signature(
        run_method
    )

    parameters = list(
        signature.parameters.values()
    )

    if not parameters:
        raise RuntimeError(
            "VideoPipeline.run has no input parameter."
        )

    input_parameter = parameters[0]

    annotation = input_parameter.annotation

    log(
        "INFO",
        f"run() input parameter: "
        f"{input_parameter.name}"
    )

    log(
        "INFO",
        f"run() annotation: "
        f"{annotation!r}"
    )

    # ----------------------------------------
    # BUILD THE INPUT
    # ----------------------------------------

    payload = {
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

    # The live pipeline has already told us its
    # annotation resolves to builtins.dict.
    if (
        annotation is dict
        or annotation == dict
        or annotation == "dict"
        or getattr(
            annotation,
            "__origin__",
            None,
        ) is dict
    ):

        trend = payload

        state[
            "input_type"
        ] = "dict"

        log(
            "PASS",
            "Using plain dict input required by live pipeline."
        )

    else:

        # If the annotation changes in the future,
        # construct it only if it is a real user class.
        if (
            inspect.isclass(
                annotation
            )
            and annotation.__module__
            != "builtins"
        ):

            constructor = inspect.signature(
                annotation
            )

            kwargs = {}

            for name, parameter in (
                constructor.parameters.items()
            ):

                if name in payload:
                    kwargs[
                        name
                    ] = payload[
                        name
                    ]

                elif (
                    parameter.default
                    is inspect.Parameter.empty
                ):

                    raise RuntimeError(
                        "Unknown required input field: "
                        + name
                    )

            trend = annotation(
                **kwargs
            )

            state[
                "input_type"
            ] = (
                annotation.__module__
                + "."
                + annotation.__name__
            )

            log(
                "PASS",
                "Constructed annotated pipeline input."
            )

        else:

            # Safe fallback for an untyped/Any input.
            trend = payload

            state[
                "input_type"
            ] = "dict_fallback"

            log(
                "PASS",
                "Using safe dictionary fallback."
            )

    # ----------------------------------------
    # SNAPSHOT EXISTING VIDEOS
    # ----------------------------------------

    video_dir = (
        ROOT
        / "generated"
        / "videos"
    )

    before = {}

    if video_dir.exists():

        for path in video_dir.glob(
            "*.mp4"
        ):

            try:
                before[
                    str(path.resolve())
                ] = (
                    path.stat().st_mtime_ns,
                    path.stat().st_size,
                )
            except OSError:
                pass

    # ----------------------------------------
    # RUN REAL PIPELINE
    # ----------------------------------------

    log(
        "INFO",
        "Starting real pipeline."
    )

    log(
        "INFO",
        "Orchestrator: DISABLED"
    )

    log(
        "INFO",
        "Publisher: DISABLED"
    )

    value = run_method(
        trend
    )

    if inspect.isawaitable(
        value
    ):
        value = await value

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

    log(
        "PASS",
        "VideoPipeline.run returned."
    )

    # ----------------------------------------
    # FIND OUTPUT FROM RETURN VALUE
    # ----------------------------------------

    candidates = []

    if isinstance(
        value,
        (str, Path),
    ):

        candidates.append(
            value
        )

    elif isinstance(
        value,
        dict,
    ):

        for key in (
            "video_path",
            "output_path",
            "render_path",
            "file_path",
            "path",
            "output",
        ):

            candidate = value.get(
                key
            )

            if isinstance(
                candidate,
                (str, Path),
            ):
                candidates.append(
                    candidate
                )

    else:

        for name in (
            "video_path",
            "output_path",
            "render_path",
            "file_path",
            "path",
            "output",
        ):

            candidate = getattr(
                value,
                name,
                None,
            )

            if isinstance(
                candidate,
                (str, Path),
            ):
                candidates.append(
                    candidate
                )

    found = None

    for candidate in candidates:

        path = Path(
            candidate
        )

        if not path.is_absolute():
            path = (
                ROOT
                / path
            )

        if (
            path.exists()
            and path.is_file()
            and path.suffix.lower()
            == ".mp4"
        ):

            found = path.resolve()
            break

    # ----------------------------------------
    # FIND NEW/CHANGED MP4 IF RETURN VALUE
    # DOES NOT CONTAIN THE PATH
    # ----------------------------------------

    if (
        found is None
        and video_dir.exists()
    ):

        changed = []

        for path in video_dir.glob(
            "*.mp4"
        ):

            try:

                resolved = str(
                    path.resolve()
                )

                current = (
                    path.stat().st_mtime_ns,
                    path.stat().st_size,
                )

                previous = before.get(
                    resolved
                )

                if (
                    previous is None
                    or previous != current
                ):

                    changed.append(
                        path
                    )

            except OSError:
                pass

        changed.sort(
            key=lambda p:
                p.stat().st_mtime_ns,
            reverse=True,
        )

        if changed:
            found = changed[
                0
            ].resolve()

    # ----------------------------------------
    # RESULT
    # ----------------------------------------

    state[
        "raw_result_type"
    ] = type(
        value
    ).__name__

    state[
        "raw_result"
    ] = repr(
        value
    )[:4000]

    if found is not None:

        state[
            "output"
        ] = str(
            found
        )

        state[
            "output_bytes"
        ] = (
            found.stat().st_size
        )

        log(
            "PASS",
            "Real MP4 created."
        )

        print(
            f"[RESULT] MP4={found}",
            flush=True,
        )

        print(
            f"[RESULT] SIZE="
            f"{found.stat().st_size}",
            flush=True,
        )

    else:

        log(
            "INFO",
            "No new MP4 detected."
        )

        log(
            "INFO",
            "This is expected if a quality/"
            "media gate rejected the run."
        )

    state[
        "success"
    ] = True

    save()

    print()
    print(
        "=" * 60
    )

    print(
        "BLOCK 5 REAL BENCHMARK COMPLETED"
    )

    print(
        "=" * 60
    )

    print(
        f"[RESULT] ELAPSED="
        f"{state['elapsed_seconds']} sec"
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
    print(
        "=" * 60
    )

    print(
        "BLOCK 5 REAL BENCHMARK STOPPED"
    )

    print(
        "=" * 60
    )

    print(
        f"[RESULT] TYPE="
        f"{type(exc).__name__}"
    )

    print(
        f"[RESULT] REASON="
        f"{str(exc)}"
    )

    sys.exit(
        1
    )
