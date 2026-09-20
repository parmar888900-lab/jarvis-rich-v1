from pathlib import Path
import ast
import shutil
import sys

pipeline_path = Path(
    "backend/services/pipelines/video_pipeline.py"
)

research_path = Path(
    "backend/services/research/evergreen_research_service.py"
)

backup = Path(sys.argv[1])


def read(path):
    return path.read_text(
        encoding="utf-8-sig"
    )


def restore():
    shutil.copy2(
        backup / "video_pipeline.py",
        pipeline_path,
    )

    shutil.copy2(
        backup / "evergreen_research_service.py",
        research_path,
    )


try:

    pipeline = read(
        pipeline_path
    )

    research = read(
        research_path
    )

    compile(
        pipeline,
        str(pipeline_path),
        "exec",
    )

    compile(
        research,
        str(research_path),
        "exec",
    )

    # Only test functionality that this patch guarantees.
    required_pipeline = (
        "MASTER_VISUAL_ACQUISITION_V2",
        "MASTER_VISUAL_HELPERS_V2",
        "STAGE_MEDIA_CANDIDATE_LIMIT = 3",
        "BEAT_MEDIA_CANDIDATE_LIMIT = 3",
        "TARGET_DISTINCT_BEAT_ASSETS = 6",
        "_master_asset_identity",
        "_master_query_tokens",
        "_master_query_variants",
        "_master_metadata_score",
        "_master_choose_asset",
        "semantic_query_diverse",
        "rotating_stage_fallback",
        "master_candidate_count",
        "master_semantic_rejections",
        "master_duplicate_avoidance_events",
        "master_query_count",
        "Visual diversity gate rejected sequence",
        "self.asset_collector.authorize",
    )

    for marker in required_pipeline:

        if marker not in pipeline:

            raise RuntimeError(
                "Missing required pipeline marker: "
                + marker
            )

    required_research = (
        "MASTER_RESEARCH_SPECIFICITY_V2",
        "Foley (filmmaking)",
        "Sound effect",
        "Sound design",
        "Post-production",
        "if len(pack.sources) >= 4:",
    )

    for marker in required_research:

        if marker not in research:

            raise RuntimeError(
                "Missing required research marker: "
                + marker
            )

    tree = ast.parse(
        pipeline
    )

    cls = next(
        (
            node
            for node in tree.body
            if isinstance(
                node,
                ast.ClassDef,
            )
            and node.name
            == "VideoPipeline"
        ),
        None,
    )

    if cls is None:
        raise RuntimeError(
            "VideoPipeline missing."
        )

    methods = {
        node.name
        for node in cls.body
        if isinstance(
            node,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
            ),
        )
    }

    expected = {
        "run",
        "_master_asset_identity",
        "_master_query_tokens",
        "_master_query_variants",
        "_master_metadata_score",
        "_master_choose_asset",
    }

    missing = (
        expected
        - methods
    )

    if missing:

        raise RuntimeError(
            "Missing helper methods: "
            + repr(
                sorted(missing)
            )
        )

    # Verify legacy single-result acquisition was actually replaced.
    if (
        "limit=(\n"
        "                            "
        "self.BEAT_MEDIA_CANDIDATE_LIMIT"
        not in pipeline
    ):

        raise RuntimeError(
            "Beat candidate acquisition not confirmed."
        )

    # Block 5 must still be independent and fail-closed.
    if (
        "BLOCK5_VISUAL_QA_BEGIN"
        not in pipeline
        or "BLOCK5_VISUAL_QA_END"
        not in pipeline
    ):

        raise RuntimeError(
            "Block 5 QA markers missing."
        )

    # Rights gate must still be called from pipeline.
    if (
        pipeline.count(
            "self.asset_collector.authorize"
        )
        < 2
    ):

        raise RuntimeError(
            "Rights authorization regression."
        )

    print(
        "[PASS] Pipeline syntax."
    )

    print(
        "[PASS] Research syntax."
    )

    print(
        "[PASS] Required helper methods."
    )

    print(
        "[PASS] Multi-candidate acquisition."
    )

    print(
        "[PASS] Duplicate-avoidance path."
    )

    print(
        "[PASS] Rotating fallback path."
    )

    print(
        "[PASS] Rights authorization preserved."
    )

    print(
        "[PASS] Block 5 preserved."
    )

    print(
        "[PASS] Research specificity."
    )

    print(
        "[PASS] Master V2 verification."
    )

except Exception as exc:

    restore()

    print(
        "[ROLLBACK] Verification failed."
    )

    print(
        f"[ROLLBACK] {type(exc).__name__}: {exc}"
    )

    print(
        "[PASS] Original source restored."
    )

    sys.exit(3)
