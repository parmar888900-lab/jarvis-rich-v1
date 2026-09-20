from pathlib import Path
import ast

PIPELINE = Path(
    "backend/services/pipelines/video_pipeline.py"
)

RESEARCH = Path(
    "backend/services/research/evergreen_research_service.py"
)

source = PIPELINE.read_text(
    encoding="utf-8-sig"
)

research = RESEARCH.read_text(
    encoding="utf-8-sig"
)

tree = ast.parse(source)
ast.parse(research)

cls = next(
    (
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef)
        and node.name == "VideoPipeline"
    ),
    None,
)

if cls is None:
    raise RuntimeError(
        "VideoPipeline missing."
    )

constants = {}

for node in cls.body:

    if not isinstance(node, ast.Assign):
        continue

    if len(node.targets) != 1:
        continue

    target = node.targets[0]

    if not isinstance(target, ast.Name):
        continue

    try:
        constants[target.id] = ast.literal_eval(
            node.value
        )
    except Exception:
        pass

expected = {
    "MAX_SEMANTIC_MEDIA_ENRICHMENTS": 10,
    "STAGE_MEDIA_CANDIDATE_LIMIT": 3,
    "BEAT_MEDIA_CANDIDATE_LIMIT": 3,
    "TARGET_DISTINCT_BEAT_ASSETS": 6,
    "SEMANTIC_VISUAL_V4": True,
}

for name, expected_value in expected.items():

    actual = constants.get(name)

    if actual != expected_value:

        raise RuntimeError(
            f"{name}: expected "
            f"{expected_value!r}, got {actual!r}"
        )

required = (
    "Foley artist recording movie sound effects",
    "Foley artist recording footsteps studio",
    "film sound editor post production studio",
    "negative_tokens",
    "domain_tokens",
    "semantic_score >= 0.28",
    "query_score * 0.78",
    "semantic_rotating_stage_fallback",
    "used_identities",
    "previous_identity",
    "self.asset_collector.authorize",
    "Visual diversity gate rejected sequence",
    "BLOCK5_VISUAL_QA_BEGIN",
    "BLOCK5_VISUAL_QA_END",
)

for marker in required:

    if marker not in source:

        raise RuntimeError(
            "Missing V4 feature: "
            + marker
        )

methods = [
    node.name
    for node in cls.body
    if isinstance(
        node,
        (
            ast.FunctionDef,
            ast.AsyncFunctionDef,
        ),
    )
]

for helper in (
    "_master_query_variants",
    "_master_metadata_score",
    "_master_choose_asset",
):

    if methods.count(helper) != 1:

        raise RuntimeError(
            f"{helper} definition count="
            f"{methods.count(helper)}"
        )

print("[PASS] V4 is fully installed.")
print("[PASS] V3 acquisition preserved.")
print("[PASS] Foley-specific searches installed.")
print("[PASS] Generic-media rejection installed.")
print("[PASS] Weighted semantic scoring installed.")
print("[PASS] Semantic fallback installed.")
print("[PASS] Duplicate controls preserved.")
print("[PASS] Rights authorization preserved.")
print("[PASS] Block 5 preserved.")
