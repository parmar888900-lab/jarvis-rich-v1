from pathlib import Path
import ast
import shutil
import sys

PIPELINE = Path(
    "backend/services/pipelines/video_pipeline.py"
)

RESEARCH = Path(
    "backend/services/research/evergreen_research_service.py"
)

# The failed V4 block restored this backup.
V3_BACKUP = Path(
    "generated/backups/semantic_visual_v4_20260919_141901"
)

# The previous patch script is known and already generated.
V4_PATCH = Path(
    "generated/diagnostics/semantic_visual_v4_20260919_141901/"
    "apply_semantic_visual_v4.py"
)

print("=" * 68)
print("V4 STATE RECOVERY")
print("=" * 68)

if not PIPELINE.exists():
    raise RuntimeError(
        "video_pipeline.py missing."
    )

if not RESEARCH.exists():
    raise RuntimeError(
        "evergreen_research_service.py missing."
    )

source = PIPELINE.read_text(
    encoding="utf-8-sig"
)

research = RESEARCH.read_text(
    encoding="utf-8-sig"
)

ast.parse(source)
ast.parse(research)

# ------------------------------------------------------------
# Determine REAL current state.
# ------------------------------------------------------------

has_v3 = (
    "MASTER_VISUAL_ACQUISITION_V2"
    in source
)

has_v4_constant = (
    "SEMANTIC_VISUAL_V4 = True"
    in source
)

has_v4_foley = (
    "Foley artist recording movie sound effects"
    in source
)

has_v4_negative = (
    "negative_tokens"
    in source
)

has_v4_fallback = (
    "semantic_rotating_stage_fallback"
    in source
)

has_v4_score = (
    "query_score * 0.78"
    in source
)

v4_complete = all(
    (
        has_v4_constant,
        has_v4_foley,
        has_v4_negative,
        has_v4_fallback,
        has_v4_score,
    )
)

print(
    f"[INFO] V3 marker: {has_v3}"
)

print(
    f"[INFO] V4 constant: {has_v4_constant}"
)

print(
    f"[INFO] V4 Foley queries: {has_v4_foley}"
)

print(
    f"[INFO] V4 generic-media filter: {has_v4_negative}"
)

print(
    f"[INFO] V4 semantic fallback: {has_v4_fallback}"
)

print(
    f"[INFO] V4 weighted scoring: {has_v4_score}"
)

if v4_complete:

    print()
    print(
        "[PASS] V4 is already fully installed."
    )

    print(
        "[PASS] No patch required."
    )

    raise SystemExit(0)

# ------------------------------------------------------------
# If only the stale marker exists, remove ONLY that marker,
# then reuse the already-created V4 patch.
# ------------------------------------------------------------

if (
    "SEMANTIC_VISUAL_V4"
    in source
    and not v4_complete
):

    print()
    print(
        "[INFO] Partial/stale V4 marker detected."
    )

    cleaned = source.replace(
        "    SEMANTIC_VISUAL_V4 = True\n",
        "",
    )

    # Also remove a possible comment-only stale marker.
    cleaned = cleaned.replace(
        "        SEMANTIC_VISUAL_V4\n",
        "",
    )

    ast.parse(cleaned)

    PIPELINE.write_text(
        cleaned,
        encoding="utf-8",
    )

    print(
        "[PASS] Stale V4 marker removed."
    )

# ------------------------------------------------------------
# Verify we are still on valid V3 before patching.
# ------------------------------------------------------------

source = PIPELINE.read_text(
    encoding="utf-8-sig"
)

if (
    "MASTER_VISUAL_ACQUISITION_V2"
    not in source
):

    raise RuntimeError(
        "V3 acquisition layer missing; refusing to patch."
    )

if not V4_PATCH.exists():

    raise RuntimeError(
        "Previous V4 patch script not found."
    )

if not V3_BACKUP.exists():

    raise RuntimeError(
        "Previous V3 backup not found."
    )

print(
    "[PASS] Valid V3 base confirmed."
)

print(
    "[PASS] Previous V4 patch script found."
)

print()
print(
    "[INFO] Recovery prepared; patch must now be executed."
)

raise SystemExit(10)
