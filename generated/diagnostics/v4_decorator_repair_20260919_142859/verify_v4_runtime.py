import inspect

from backend.services.pipelines.video_pipeline import VideoPipeline

print("===== EXACT RUNTIME DESCRIPTOR TEST =====")

targets = (
    "_master_query_variants",
    "_master_metadata_score",
    "_master_choose_asset",
)

for name in targets:
    raw = inspect.getattr_static(VideoPipeline, name)

    if not isinstance(raw, classmethod):
        raise RuntimeError(
            f"{name}: raw descriptor is "
            f"{type(raw).__name__}, not classmethod"
        )

    if isinstance(raw.__func__, classmethod):
        raise RuntimeError(
            f"{name}: nested classmethod still exists"
        )

    bound = getattr(VideoPipeline, name)

    if not callable(bound):
        raise RuntimeError(
            f"{name}: bound value is not callable"
        )

    print(
        f"[PASS] {name}: single descriptor -> callable"
    )


class DummyBeat:
    search_query = "movie footsteps sound effects"
    visual_requirement = "Foley artist recording footsteps"
    purpose = "show how film footsteps are recreated"


queries = VideoPipeline._master_query_variants(
    topic="Why movie sound effects are often recorded separately",
    beat=DummyBeat(),
)

if not isinstance(queries, list) or not queries:
    raise RuntimeError(
        "_master_query_variants execution failed."
    )

print("[PASS] _master_query_variants executed.")
print(f"[INFO] Query 1: {queries[0]}")

if len(queries) > 1:
    print(f"[INFO] Query 2: {queries[1]}")


class DummyAsset:
    asset_type = "image"
    title = "Foley artist recording footsteps for film"
    description = "Movie sound effects recording studio"
    source_url = "https://example.invalid/foley"
    asset_id = "runtime-test"
    local_path = "runtime-test.jpg"


score = VideoPipeline._master_metadata_score(
    asset=DummyAsset(),
    query="Foley artist recording footsteps studio",
    topic="Why movie sound effects are often recorded separately",
)

if not isinstance(score, (int, float)):
    raise RuntimeError(
        "_master_metadata_score did not return numeric score."
    )

print(
    f"[PASS] _master_metadata_score executed: {score:.3f}"
)

chosen = VideoPipeline._master_choose_asset(
    candidates=[DummyAsset()],
    query="Foley artist recording footsteps studio",
    topic="Why movie sound effects are often recorded separately",
    used_identities=set(),
    previous_identity="",
)

if chosen is None:
    raise RuntimeError(
        "_master_choose_asset rejected known-good runtime fixture."
    )

print("[PASS] _master_choose_asset executed.")
print("[PASS] Previous 'classmethod object is not callable' boundary cleared.")
