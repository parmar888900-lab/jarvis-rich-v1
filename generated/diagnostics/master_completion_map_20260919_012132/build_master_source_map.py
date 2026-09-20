from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path


ROOT = Path.cwd()
STAMP = sys.argv[1]

OUT = (
    ROOT
    / "generated"
    / "diagnostics"
    / f"master_completion_map_{STAMP}"
    / "MASTER_SOURCE_MAP.txt"
)

SECTIONS = []


def emit(title, text=""):
    SECTIONS.append(
        "\n"
        + "=" * 78
        + "\n"
        + title
        + "\n"
        + "=" * 78
        + "\n"
        + text.rstrip()
        + "\n"
    )


def read(path):
    return path.read_text(
        encoding="utf-8-sig"
    )


def numbered(text, start=1):
    lines = text.splitlines()

    return "\n".join(
        f"{i:5d}: {line}"
        for i, line in enumerate(
            lines,
            start=start,
        )
    )


def source_segment(text, node):
    lines = text.splitlines()

    start = max(
        1,
        node.lineno - 8,
    )

    end = min(
        len(lines),
        node.end_lineno + 8,
    )

    return numbered(
        "\n".join(
            lines[
                start - 1:end
            ]
        ),
        start,
    )


def methods_with_keywords(
    path,
    keywords,
):
    text = read(path)

    try:
        tree = ast.parse(
            text
        )
    except Exception as exc:
        return (
            f"AST ERROR: {exc}\n"
        )

    found = []

    for node in ast.walk(
        tree
    ):

        if not isinstance(
            node,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
            ),
        ):
            continue

        segment = ast.get_source_segment(
            text,
            node,
        ) or ""

        haystack = (
            node.name
            + "\n"
            + segment
        ).lower()

        if any(
            keyword.lower()
            in haystack
            for keyword in keywords
        ):

            owner = ""

            for parent in ast.walk(
                tree
            ):

                if not isinstance(
                    parent,
                    ast.ClassDef,
                ):
                    continue

                if node in parent.body:
                    owner = (
                        parent.name
                        + "."
                    )
                    break

            found.append(
                (
                    node.lineno,
                    owner
                    + node.name,
                    source_segment(
                        text,
                        node,
                    ),
                )
            )

    found.sort(
        key=lambda item:
            item[0]
    )

    if not found:
        return "NO MATCHING METHODS\n"

    chunks = []

    for line, name, segment in found:

        chunks.append(
            f"\n--- {name} @ line {line} ---\n"
            + segment
            + "\n"
        )

    return "".join(
        chunks
    )


def grep_context(
    path,
    patterns,
    radius=8,
):
    text = read(path)
    lines = text.splitlines()

    hits = []

    regexes = [
        re.compile(
            pattern,
            re.I,
        )
        for pattern in patterns
    ]

    seen = set()

    for index, line in enumerate(
        lines
    ):

        if not any(
            regex.search(
                line
            )
            for regex in regexes
        ):
            continue

        start = max(
            0,
            index - radius,
        )

        end = min(
            len(lines),
            index + radius + 1,
        )

        key = (
            start,
            end,
        )

        if key in seen:
            continue

        seen.add(
            key
        )

        hits.append(
            numbered(
                "\n".join(
                    lines[
                        start:end
                    ]
                ),
                start + 1,
            )
        )

    if not hits:
        return "NO MATCHES\n"

    return (
        "\n\n--- CONTEXT ---\n\n"
    ).join(
        hits
    )


def file_inventory():
    roots = [
        ROOT / "backend" / "services",
        ROOT / "backend",
    ]

    keywords = (
        "media",
        "asset",
        "video_pipeline",
        "renderer",
        "research",
        "production",
        "scheduler",
        "watchdog",
        "topic",
        "premise",
        "clip",
        "matcher",
        "wikimedia",
        "pexels",
        "audio",
        "caption",
    )

    paths = set()

    for base in roots:

        if not base.exists():
            continue

        for path in base.rglob(
            "*.py"
        ):

            lowered = str(
                path.relative_to(
                    ROOT
                )
            ).lower()

            if any(
                key in lowered
                for key in keywords
            ):
                paths.add(
                    path
                )

    return sorted(
        paths,
        key=lambda p:
            str(p)
    )


PIPELINE = (
    ROOT
    / "backend"
    / "services"
    / "pipelines"
    / "video_pipeline.py"
)

GENERATOR = (
    ROOT
    / "backend"
    / "services"
    / "content_generator.py"
)

RENDERER = (
    ROOT
    / "backend"
    / "services"
    / "video_renderer"
    / "renderer.py"
)

WIKIMEDIA = (
    ROOT
    / "backend"
    / "services"
    / "video"
    / "media_sources"
    / "wikimedia.py"
)

APP = (
    ROOT
    / "backend"
    / "app.py"
)


emit(
    "1. RELEVANT PYTHON FILE INVENTORY",
    "\n".join(
        str(
            path.relative_to(
                ROOT
            )
        )
        for path in file_inventory()
    ),
)


if PIPELINE.exists():

    emit(
        "2. VIDEO PIPELINE - MEDIA / ASSET / SEMANTIC METHODS",
        methods_with_keywords(
            PIPELINE,
            (
                "media",
                "asset",
                "semantic",
                "image",
                "beat",
                "collect",
                "authorize",
                "render",
                "query",
                "visual",
                "fallback",
            ),
        ),
    )

    emit(
        "3. VIDEO PIPELINE - EXACT ACQUISITION CONTEXT",
        grep_context(
            PIPELINE,
            (
                r"search_and_download",
                r"authorize\(",
                r"beat_render_assets",
                r"semantic_media",
                r"MAX_SEMANTIC",
                r"visual_quality",
                r"BLOCK5",
                r"fallback",
                r"beat_images",
                r"search_query",
                r"visual_requirement",
            ),
            radius=14,
        ),
    )


if WIKIMEDIA.exists():

    emit(
        "4. WIKIMEDIA PROVIDER - RELEVANT METHODS",
        methods_with_keywords(
            WIKIMEDIA,
            (
                "search_and_download",
                "_search_and_download_sync",
                "_api",
                "_download",
                "relevance",
                "license",
            ),
        ),
    )


# Find collector / authorization implementations.
collector_sections = []

for path in file_inventory():

    text = read(
        path
    )

    if (
        "def authorize" in text
        or "async def authorize" in text
        or "class AssetCollector" in text
        or "class MediaAsset" in text
    ):

        collector_sections.append(
            "\nFILE: "
            + str(
                path.relative_to(
                    ROOT
                )
            )
            + "\n"
            + methods_with_keywords(
                path,
                (
                    "authorize",
                    "collect",
                    "asset",
                    "rights",
                    "license",
                ),
            )
        )

emit(
    "5. ASSET COLLECTOR / RIGHTS INTERFACES",
    "\n".join(
        collector_sections
    )
    if collector_sections
    else "NO COLLECTOR MATCHES\n",
)


# Search for existing ClipMatcher/OpenCLIP implementation.
matcher_sections = []

for path in file_inventory():

    text = read(
        path
    )

    if any(
        token in text
        for token in (
            "ClipMatcher",
            "OpenCLIP",
            "open_clip",
            "semantic_similarity",
            "clip_score",
        )
    ):

        matcher_sections.append(
            "\nFILE: "
            + str(
                path.relative_to(
                    ROOT
                )
            )
            + "\n"
            + methods_with_keywords(
                path,
                (
                    "clip",
                    "match",
                    "semantic",
                    "similarity",
                    "score",
                ),
            )
        )

emit(
    "6. EXISTING CLIP / SEMANTIC MATCHER",
    "\n".join(
        matcher_sections
    )
    if matcher_sections
    else "NO EXISTING CLIP MATCHER FOUND\n",
)


# Research stack.
research_sections = []

for path in file_inventory():

    text = read(
        path
    )

    if (
        "EvergreenResearch" in text
        or "KnowledgePack" in text
        or "def research" in text
        or "async def research" in text
    ):

        research_sections.append(
            "\nFILE: "
            + str(
                path.relative_to(
                    ROOT
                )
            )
            + "\n"
            + methods_with_keywords(
                path,
                (
                    "research",
                    "query",
                    "knowledge",
                    "source",
                    "evergreen",
                    "topic",
                ),
            )
        )

emit(
    "7. RESEARCH STACK",
    "\n".join(
        research_sections
    )
    if research_sections
    else "NO RESEARCH MATCHES\n",
)


if GENERATOR.exists():

    emit(
        "8. CONTENT GENERATOR - MOVIE / RECOVERY / EVIDENCE",
        methods_with_keywords(
            GENERATOR,
            (
                "movie",
                "recover",
                "evidence",
                "script",
                "generate",
                "premise",
            ),
        ),
    )


if RENDERER.exists():

    emit(
        "9. RENDERER - BLOCK5 / BEATS / AUDIO / CAPTIONS",
        methods_with_keywords(
            RENDERER,
            (
                "beat",
                "image",
                "caption",
                "audio",
                "music",
                "sfx",
                "render",
                "visual",
            ),
        ),
    )

    emit(
        "10. RENDERER - QUALITY CONTEXT",
        grep_context(
            RENDERER,
            (
                r"BLOCK5",
                r"beat_images",
                r"caption",
                r"zoom",
                r"music",
                r"sfx",
                r"audio",
                r"duration",
            ),
            radius=10,
        ),
    )


# Production/autonomy.
production_sections = []

for path in file_inventory():

    text = read(
        path
    )

    if any(
        token in text
        for token in (
            "DailyProductionBatch",
            "ProductionScheduler",
            "ProductionOrchestrator",
            "daily_target",
            "cooldown_until",
            "attempts_per_pass",
        )
    ):

        production_sections.append(
            "\nFILE: "
            + str(
                path.relative_to(
                    ROOT
                )
            )
            + "\n"
            + methods_with_keywords(
                path,
                (
                    "daily",
                    "production",
                    "scheduler",
                    "cooldown",
                    "attempt",
                    "success",
                    "release",
                ),
            )
        )

emit(
    "11. PRODUCTION / DAILY AUTONOMY",
    "\n".join(
        production_sections
    )
    if production_sections
    else "NO PRODUCTION MATCHES\n",
)


if APP.exists():

    emit(
        "12. APP STARTUP / DAILY SUPERVISOR",
        grep_context(
            APP,
            (
                r"daily_production",
                r"production_scheduler",
                r"production_ready",
                r"scheduler_enabled",
                r"create_task",
            ),
            radius=14,
        ),
    )


# Watchdog is PowerShell, not Python.
watchdog = (
    ROOT
    / "jarvis_watchdog.ps1"
)

if watchdog.exists():

    emit(
        "13. WATCHDOG V3 CURRENT SOURCE",
        numbered(
            read(
                watchdog
            )
        ),
    )


# Current quality markers.
markers = {}

checks = {
    "pipeline_block5":
        (
            PIPELINE,
            "BLOCK5_VISUAL_QA_BEGIN",
        ),

    "renderer_block5":
        (
            RENDERER,
            "BLOCK5_RENDERER_QA_BEGIN",
        ),

    "semantic_enrichment":
        (
            PIPELINE,
            "MAX_SEMANTIC_MEDIA_ENRICHMENTS",
        ),

    "rights_authorize":
        (
            PIPELINE,
            "authorize(",
        ),

    "evidence_validator":
        (
            GENERATOR,
            "claim_evidence_validator.validate",
        ),

    "wikimedia_retry_after":
        (
            WIKIMEDIA,
            "Retry-After",
        ),
}

for name, (
    path,
    marker,
) in checks.items():

    markers[
        name
    ] = (
        path.exists()
        and marker in read(
            path
        )
    )

emit(
    "14. CURRENT QUALITY/SAFETY MARKERS",
    json.dumps(
        markers,
        indent=2,
    ),
)


# Syntax-only validation. No imports = no service startup.
compile_results = {}

for path in file_inventory():

    try:

        compile(
            read(
                path
            ),
            str(
                path
            ),
            "exec",
        )

        compile_results[
            str(
                path.relative_to(
                    ROOT
                )
            )
        ] = "PASS"

    except Exception as exc:

        compile_results[
            str(
                path.relative_to(
                    ROOT
                )
            )
        ] = (
            type(
                exc
            ).__name__
            + ": "
            + str(
                exc
            )
        )

emit(
    "15. READ-ONLY SYNTAX CHECK",
    json.dumps(
        compile_results,
        indent=2,
    ),
)


OUT.write_text(
    "".join(
        SECTIONS
    ),
    encoding="utf-8",
)

print(
    "[PASS] Master source map created."
)

print(
    f"[RESULT] {OUT}"
)

print(
    "[PASS] No source files modified."
)

print(
    "[PASS] No modules imported from Jarvis."
)

print(
    "[PASS] No network requests."
)

print(
    "[PASS] No generation/render/upload."
)

print(
    "[PASS] No restart."
)
