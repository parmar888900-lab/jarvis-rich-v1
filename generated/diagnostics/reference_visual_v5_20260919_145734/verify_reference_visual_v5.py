import ast
import inspect
import sys
from pathlib import Path

ROOT = Path.cwd().resolve()

if str(ROOT) not in sys.path:
    sys.path.insert(
        0,
        str(ROOT),
    )

PIPELINE = Path(
    "backend/services/pipelines/video_pipeline.py"
)

source = PIPELINE.read_text(
    encoding="utf-8-sig"
)

tree = ast.parse(source)

from backend.services.pipelines.video_pipeline import VideoPipeline

print(
    "===== V5 RUNTIME VERIFICATION ====="
)

if not getattr(
    VideoPipeline,
    "REFERENCE_VISUAL_V5",
    False,
):
    raise RuntimeError(
        "V5 runtime marker missing."
    )

for name in (
    "_master_query_variants",
    "_master_metadata_score",
    "_master_choose_asset",
):

    raw = inspect.getattr_static(
        VideoPipeline,
        name,
    )

    if not isinstance(
        raw,
        classmethod,
    ):
        raise RuntimeError(
            f"{name} is not a classmethod."
        )

    if isinstance(
        raw.__func__,
        classmethod,
    ):
        raise RuntimeError(
            f"{name} has nested classmethod."
        )

    bound = getattr(
        VideoPipeline,
        name,
    )

    if not callable(bound):
        raise RuntimeError(
            f"{name} is not callable."
        )

    print(
        f"[PASS] {name}"
    )


class FootstepBeat:
    search_query = (
        "footsteps sound effects"
    )
    visual_requirement = (
        "artist recreating footsteps"
    )
    purpose = (
        "show how footsteps are recreated"
    )


class EditBeat:
    search_query = (
        "movie sound editing"
    )
    visual_requirement = (
        "sound editor working on audio timeline"
    )
    purpose = (
        "show sounds being edited after filming"
    )


class ADRBeat:
    search_query = (
        "dialogue replacement"
    )
    visual_requirement = (
        "actor recording dialogue"
    )
    purpose = (
        "show dialogue recorded separately"
    )


footstep_queries = (
    VideoPipeline._master_query_variants(
        topic=(
            "Why movie sound effects are "
            "often recorded separately"
        ),
        beat=FootstepBeat(),
    )
)

edit_queries = (
    VideoPipeline._master_query_variants(
        topic=(
            "Why movie sound effects are "
            "often recorded separately"
        ),
        beat=EditBeat(),
    )
)

adr_queries = (
    VideoPipeline._master_query_variants(
        topic=(
            "Why movie sound effects are "
            "often recorded separately"
        ),
        beat=ADRBeat(),
    )
)

if not any(
    "footstep" in query.lower()
    for query in footstep_queries
):
    raise RuntimeError(
        "Footstep visual routing failed."
    )

if not any(
    (
        "editor" in query.lower()
        or "editing" in query.lower()
    )
    for query in edit_queries
):
    raise RuntimeError(
        "Editing visual routing failed."
    )

if not any(
    (
        "adr" in query.lower()
        or "dialogue" in query.lower()
    )
    for query in adr_queries
):
    raise RuntimeError(
        "ADR visual routing failed."
    )

print(
    "[PASS] Footstep visual routing."
)

print(
    "[PASS] Sound-editing visual routing."
)

print(
    "[PASS] ADR visual routing."
)

print(
    "[INFO] Footstep queries:"
)

for query in footstep_queries:
    print(
        "       " + query
    )

print(
    "[INFO] Editing queries:"
)

for query in edit_queries:
    print(
        "       " + query
    )

print(
    "[INFO] ADR queries:"
)

for query in adr_queries:
    print(
        "       " + query
    )

print(
    "[PASS] V5 runtime verification passed."
)
