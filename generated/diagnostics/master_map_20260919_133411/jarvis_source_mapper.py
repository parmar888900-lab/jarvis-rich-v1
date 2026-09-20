from __future__ import annotations

import ast
import sys
from pathlib import Path


ROOT = Path.cwd()
OUT = Path(sys.argv[1])

SEARCH_ROOTS = [
    ROOT / "backend",
]

NAME_TERMS = (
    "video_pipeline",
    "renderer",
    "media",
    "asset",
    "wikimedia",
    "pexels",
    "clip",
    "matcher",
    "research",
    "content_generator",
    "production",
    "scheduler",
    "orchestrator",
    "topic",
    "premise",
)

SOURCE_TERMS = (
    "beat_render_assets",
    "semantic_media",
    "search_and_download",
    "authorize(",
    "visual_quality",
    "MAX_SEMANTIC_MEDIA_ENRICHMENTS",
    "visual_requirement",
    "search_query",
    "fallback",
    "ClipMatcher",
    "open_clip",
    "EvergreenResearch",
    "KnowledgePack",
    "claim_evidence_validator",
    "DailyProductionBatch",
    "ProductionScheduler",
    "cooldown_until",
    "attempts_per_pass",
    "daily_target",
)

IMPORTANT_METHOD_TERMS = (
    "media",
    "asset",
    "semantic",
    "visual",
    "beat",
    "image",
    "collect",
    "authorize",
    "search",
    "download",
    "research",
    "query",
    "render",
    "clip",
    "match",
    "fallback",
    "production",
    "daily",
    "scheduler",
    "cooldown",
    "generate",
    "recover",
    "evidence",
)


def read(path: Path) -> str:
    return path.read_text(
        encoding="utf-8-sig",
        errors="replace",
    )


def relative(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except Exception:
        return str(path)


def numbered(lines, start):
    return "\n".join(
        f"{i:5d}: {line}"
        for i, line in enumerate(lines, start)
    )


def context_hits(text, radius=12):
    lines = text.splitlines()
    indexes = set()

    for i, line in enumerate(lines):
        lower = line.lower()

        if any(
            term.lower() in lower
            for term in SOURCE_TERMS
        ):
            for j in range(
                max(0, i - radius),
                min(len(lines), i + radius + 1),
            ):
                indexes.add(j)

    if not indexes:
        return ""

    groups = []
    current = []
    previous = None

    for idx in sorted(indexes):
        if previous is None or idx == previous + 1:
            current.append(idx)
        else:
            groups.append(current)
            current = [idx]

        previous = idx

    if current:
        groups.append(current)

    chunks = []

    for group in groups:
        start = group[0]
        end = group[-1] + 1

        chunks.append(
            numbered(
                lines[start:end],
                start + 1,
            )
        )

    return "\n\n--- CONTEXT ---\n\n".join(chunks)


def important_methods(path, text):
    try:
        tree = ast.parse(text)
    except Exception as exc:
        return f"AST ERROR: {type(exc).__name__}: {exc}\n"

    lines = text.splitlines()
    results = []

    class_map = {}

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for child in node.body:
                class_map[id(child)] = node.name

    for node in ast.walk(tree):
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

        if not any(
            term.lower() in haystack
            for term in IMPORTANT_METHOD_TERMS
        ):
            continue

        start = max(
            0,
            node.lineno - 5,
        )

        end_line = getattr(
            node,
            "end_lineno",
            node.lineno,
        )

        end = min(
            len(lines),
            end_line + 5,
        )

        owner = class_map.get(
            id(node)
        )

        name = (
            f"{owner}.{node.name}"
            if owner
            else node.name
        )

        results.append(
            (
                node.lineno,
                name,
                numbered(
                    lines[start:end],
                    start + 1,
                ),
            )
        )

    results.sort(
        key=lambda item: item[0]
    )

    return "\n".join(
        f"\n--- {name} @ line {line} ---\n{source}\n"
        for line, name, source in results
    )


all_python = []

for base in SEARCH_ROOTS:
    if base.exists():
        all_python.extend(
            base.rglob("*.py")
        )

all_python = sorted(
    set(all_python),
    key=lambda p: relative(p).lower(),
)

relevant = []

for path in all_python:
    try:
        text = read(path)
    except Exception:
        continue

    rel = relative(path).lower()

    name_match = any(
        term.lower() in rel
        for term in NAME_TERMS
    )

    source_match = any(
        term.lower() in text.lower()
        for term in SOURCE_TERMS
    )

    if name_match or source_match:
        relevant.append(path)


sections = []

sections.append(
    "=" * 90
    + "\nJARVIS MASTER COMPLETION SOURCE MAP\n"
    + "=" * 90
    + "\n"
)

sections.append(
    "\nRELEVANT FILE INVENTORY\n"
    + "-" * 90
    + "\n"
    + "\n".join(
        relative(path)
        for path in relevant
    )
    + "\n"
)


compile_failures = []

for path in relevant:
    text = read(path)

    try:
        compile(
            text,
            str(path),
            "exec",
        )
        compile_status = "PASS"
    except Exception as exc:
        compile_status = (
            f"FAIL - {type(exc).__name__}: {exc}"
        )
        compile_failures.append(
            f"{relative(path)} -> {compile_status}"
        )

    context = context_hits(text)

    methods = important_methods(
        path,
        text,
    )

    if not context and not methods:
        continue

    sections.append(
        "\n\n"
        + "=" * 90
        + f"\nFILE: {relative(path)}\n"
        + f"SYNTAX: {compile_status}\n"
        + "=" * 90
        + "\n"
    )

    if context:
        sections.append(
            "\nEXACT RELEVANT CONTEXT\n"
            + "-" * 90
            + "\n"
            + context
            + "\n"
        )

    if methods:
        sections.append(
            "\nIMPORTANT METHODS\n"
            + "-" * 90
            + "\n"
            + methods
            + "\n"
        )


extra_files = [
    ROOT / "backend" / "app.py",
    ROOT / "jarvis_watchdog.ps1",
]

for path in extra_files:
    if not path.exists():
        continue

    text = read(path)

    sections.append(
        "\n\n"
        + "=" * 90
        + f"\nEXTRA FILE: {relative(path)}\n"
        + "=" * 90
        + "\n"
    )

    if path.suffix.lower() == ".py":
        relevant_context = context_hits(
            text,
            radius=15,
        )

        if relevant_context:
            sections.append(
                relevant_context
            )
        else:
            sections.append(
                text
            )

    else:
        sections.append(
            text
        )


markers = {
    "block5_pipeline_visual_gate":
        "Visual diversity gate rejected sequence",

    "semantic_enrichment":
        "MAX_SEMANTIC_MEDIA_ENRICHMENTS",

    "rights_authorization":
        "authorize(",

    "evidence_validation":
        "claim_evidence_validator",

    "wikimedia_retry_after":
        "Retry-After",

    "daily_batch":
        "DailyProductionBatch",

    "production_scheduler":
        "ProductionScheduler",
}

combined = "\n".join(
    read(path)
    for path in relevant
    if path.exists()
)

sections.append(
    "\n\n"
    + "=" * 90
    + "\nPROVEN FEATURE MARKERS\n"
    + "=" * 90
    + "\n"
)

for name, marker in markers.items():
    present = marker in combined

    sections.append(
        f"{name}: {'PASS' if present else 'NOT CONFIRMED'}\n"
    )


sections.append(
    "\n\n"
    + "=" * 90
    + "\nSYNTAX SUMMARY\n"
    + "=" * 90
    + "\n"
)

if compile_failures:
    sections.extend(
        failure + "\n"
        for failure in compile_failures
    )
else:
    sections.append(
        "PASS - all mapped Python files compile.\n"
    )


sections.append(
    "\n\n"
    + "=" * 90
    + "\nEND OF SOURCE MAP\n"
    + "=" * 90
    + "\n"
)


OUT.write_text(
    "".join(sections),
    encoding="utf-8",
)

print("[PASS] Full source map written to TXT.")
print(f"[RESULT] {OUT}")
print(f"[INFO] Relevant Python files: {len(relevant)}")
print(
    "[INFO] Syntax failures: "
    + str(len(compile_failures))
)
print("[PASS] No Jarvis source modified.")
print("[PASS] No Jarvis modules imported.")
print("[PASS] No network requests.")
print("[PASS] No render.")
print("[PASS] No upload.")
print("[PASS] No daily-state reset.")
print("[PASS] No restart.")
