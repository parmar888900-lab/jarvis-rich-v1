import inspect
import sys
from pathlib import Path

ROOT = Path.cwd().resolve()

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.services.pipelines.video_pipeline import VideoPipeline

print("===== V4 RUNTIME TEST =====")

targets = (
    "_master_query_variants",
    "_master_metadata_score",
    "_master_choose_asset",
)

for name in targets:
    raw = inspect.getattr_static(
        VideoPipeline,
        name,
    )

    if not isinstance(raw, classmethod):
        raise RuntimeError(
            f"{name}: expected classmethod, "
            f"got {type(raw).__name__}"
        )

    if isinstance(raw.__func__, classmethod):
        raise RuntimeError(
            f"{name}: nested classmethod remains"
        )

    bound = getattr(
        VideoPipeline,
        name,
    )

    if not callable(bound):
        raise RuntimeError(
            f"{name}: bound descriptor is not callable"
        )

    print(
        f"[PASS] {name}: descriptor is valid."
    )


class DummyBeat:
    search_query = "movie footsteps sound effects"
    visual_requirement = "Foley artist recording footsteps"
    purpose = "show film footsteps being recreated"


queries = VideoPipeline._master_query_variants(
    topic="Why movie sound effects are often recorded separately",
    beat=DummyBeat(),
)

if not isinstance(queries, list):
    raise RuntimeError(
        "Query helper did not return a list."
    )

if not queries:
    raise RuntimeError(
        "Query helper returned no queries."
    )

print("[PASS] Query helper executed.")

for index, query in enumerate(
    queries,
    start=1,
):
    print(
        f"[INFO] Query {index}: {query}"
    )


class DummyAsset:
    asset_type = "image"
    title = "Foley artist recording footsteps for film"
    description = (
        "Movie sound effects recording in a Foley studio"
    )
    source_url = "https://example.invalid/foley"
    asset_id = "runtime-test-foley"
    local_path = "runtime-test-foley.jpg"


asset = DummyAsset()

score = VideoPipeline._master_metadata_score(
    asset=asset,
    query="Foley artist recording footsteps studio",
    topic="Why movie sound effects are often recorded separately",
)

if not isinstance(score, (int, float)):
    raise RuntimeError(
        "Metadata scorer returned non-numeric result."
    )

print(
    f"[PASS] Metadata scorer executed: {score:.3f}"
)

chosen = VideoPipeline._master_choose_asset(
    candidates=[asset],
    query="Foley artist recording footsteps studio",
    topic="Why movie sound effects are often recorded separately",
    used_identities=set(),
    previous_identity="",
)

if chosen is None:
    raise RuntimeError(
        "Known-good Foley fixture was rejected."
    )

print("[PASS] Asset selector executed.")
print(
    "[PASS] 'classmethod object is not callable' defect is cleared."
)
