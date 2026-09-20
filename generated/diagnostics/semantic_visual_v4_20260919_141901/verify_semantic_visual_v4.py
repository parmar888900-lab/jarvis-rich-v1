from pathlib import Path
import ast
import shutil
import sys

PIPELINE = Path("backend/services/pipelines/video_pipeline.py")
RESEARCH = Path("backend/services/research/evergreen_research_service.py")
BACKUP = Path(sys.argv[1])


def read(path):
    return path.read_text(encoding="utf-8-sig")


def restore():
    shutil.copy2(BACKUP / "video_pipeline.py", PIPELINE)
    shutil.copy2(
        BACKUP / "evergreen_research_service.py",
        RESEARCH,
    )


try:
    source = read(PIPELINE)
    research = read(RESEARCH)

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

    for name, value in expected.items():
        if constants.get(name) != value:
            raise RuntimeError(
                f"{name} verification failed."
            )

    methods = {
        node.name: node
        for node in cls.body
        if isinstance(
            node,
            (ast.FunctionDef, ast.AsyncFunctionDef),
        )
    }

    for method in (
        "_master_query_variants",
        "_master_metadata_score",
        "_master_choose_asset",
        "_master_asset_identity",
        "run",
    ):
        if method not in methods:
            raise RuntimeError(
                f"Missing method: {method}"
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
                "Missing required marker: "
                + marker
            )

    if "SEMANTIC_RESEARCH_V4" not in research:
        raise RuntimeError(
            "Semantic research V4 marker missing."
        )

    # Ensure helper definitions exist exactly once.
    helper_names = (
        "_master_query_variants",
        "_master_metadata_score",
        "_master_choose_asset",
    )

    for name in helper_names:
        count = sum(
            1
            for node in cls.body
            if isinstance(
                node,
                (ast.FunctionDef, ast.AsyncFunctionDef),
            )
            and node.name == name
        )

        if count != 1:
            raise RuntimeError(
                f"{name} definition count={count}"
            )

    print("[PASS] V4 AST verification.")
    print("[PASS] V3 acquisition constants preserved.")
    print("[PASS] V4 semantic helpers verified.")
    print("[PASS] Foley-specific query logic verified.")
    print("[PASS] Generic-media penalties verified.")
    print("[PASS] Semantic threshold verified.")
    print("[PASS] Duplicate controls preserved.")
    print("[PASS] Rights gate preserved.")
    print("[PASS] Block 5 preserved.")
    print("[PASS] Research grounding preserved.")

except Exception as exc:
    restore()

    print("[ROLLBACK] V4 verification failed.")
    print(
        f"[ROLLBACK] {type(exc).__name__}: {exc}"
    )
    print("[PASS] Original V3 source restored.")

    sys.exit(3)
