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


def attr_name(node):
    """
    Return dotted AST name when possible.
    Example:
    self.media_provider.search_and_download
    """

    parts = []

    current = node

    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value

    if isinstance(current, ast.Name):
        parts.append(current.id)

    return ".".join(
        reversed(parts)
    )


try:

    pipeline = read(
        pipeline_path
    )

    research = read(
        research_path
    )

    # =====================================================
    # 1. REAL PYTHON PARSE
    # =====================================================

    pipeline_tree = ast.parse(
        pipeline,
        filename=str(
            pipeline_path
        ),
    )

    research_tree = ast.parse(
        research,
        filename=str(
            research_path
        ),
    )

    print(
        "[PASS] Pipeline AST parse."
    )

    print(
        "[PASS] Research AST parse."
    )

    # =====================================================
    # 2. FIND VIDEOPIPELINE CLASS
    # =====================================================

    pipeline_class = next(
        (
            node
            for node in pipeline_tree.body
            if isinstance(
                node,
                ast.ClassDef,
            )
            and node.name
            == "VideoPipeline"
        ),
        None,
    )

    if pipeline_class is None:
        raise RuntimeError(
            "VideoPipeline class missing."
        )

    # =====================================================
    # 3. VERIFY CLASS CONSTANTS STRUCTURALLY
    # =====================================================

    constants = {}

    for node in pipeline_class.body:

        if not isinstance(
            node,
            ast.Assign,
        ):
            continue

        if len(node.targets) != 1:
            continue

        target = node.targets[0]

        if not isinstance(
            target,
            ast.Name,
        ):
            continue

        try:
            value = ast.literal_eval(
                node.value
            )
        except Exception:
            continue

        constants[
            target.id
        ] = value

    expected_constants = {
        "MAX_SEMANTIC_MEDIA_ENRICHMENTS": 10,
        "STAGE_MEDIA_CANDIDATE_LIMIT": 3,
        "BEAT_MEDIA_CANDIDATE_LIMIT": 3,
        "TARGET_DISTINCT_BEAT_ASSETS": 6,
    }

    for name, expected in (
        expected_constants.items()
    ):

        actual = constants.get(
            name
        )

        if actual != expected:

            raise RuntimeError(
                f"{name} expected "
                f"{expected}, got {actual!r}."
            )

    print(
        "[PASS] Acquisition constants structurally verified."
    )

    # =====================================================
    # 4. VERIFY REQUIRED METHODS
    # =====================================================

    methods = {
        node.name: node
        for node in pipeline_class.body
        if isinstance(
            node,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
            ),
        )
    }

    required_methods = (
        "run",
        "_master_asset_identity",
        "_master_query_tokens",
        "_master_query_variants",
        "_master_metadata_score",
        "_master_choose_asset",
    )

    for name in required_methods:

        if name not in methods:

            raise RuntimeError(
                "Missing method: "
                + name
            )

    print(
        "[PASS] Master helper methods structurally verified."
    )

    run_node = methods["run"]

    # =====================================================
    # 5. INSPECT REAL search_and_download() CALLS
    # =====================================================

    search_calls = []

    for node in ast.walk(
        run_node
    ):

        if not isinstance(
            node,
            ast.Call,
        ):
            continue

        called = attr_name(
            node.func
        )

        if not called.endswith(
            ".search_and_download"
        ):
            continue

        limit_expression = None

        for keyword in node.keywords:

            if keyword.arg == "limit":

                limit_expression = (
                    ast.unparse(
                        keyword.value
                    )
                )

                break

        search_calls.append(
            limit_expression
        )

    if not search_calls:

        raise RuntimeError(
            "No media search calls found."
        )

    print(
        "[INFO] Media search limit expressions: "
        + repr(
            search_calls
        )
    )

    normalized = {
        str(value)
        .replace(" ", "")
        .replace("\n", "")
        for value in search_calls
        if value
    }

    stage_ok = any(
        "self.STAGE_MEDIA_CANDIDATE_LIMIT"
        .replace(" ", "")
        in value
        for value in normalized
    )

    beat_ok = any(
        "self.BEAT_MEDIA_CANDIDATE_LIMIT"
        .replace(" ", "")
        in value
        for value in normalized
    )

    if not stage_ok:

        raise RuntimeError(
            "Stage multi-candidate acquisition "
            "not present in AST."
        )

    if not beat_ok:

        raise RuntimeError(
            "Beat multi-candidate acquisition "
            "not present in AST."
        )

    print(
        "[PASS] Stage acquisition uses candidate limit."
    )

    print(
        "[PASS] Beat acquisition uses candidate limit."
    )

    # =====================================================
    # 6. VERIFY RIGHTS AUTHORIZATION CALLS
    # =====================================================

    authorize_calls = 0

    for node in ast.walk(
        run_node
    ):

        if not isinstance(
            node,
            ast.Call,
        ):
            continue

        called = attr_name(
            node.func
        )

        if called.endswith(
            ".asset_collector.authorize"
        ):

            authorize_calls += 1

    if authorize_calls < 2:

        raise RuntimeError(
            "Expected at least two rights "
            "authorization paths."
        )

    print(
        "[PASS] Rights authorization calls preserved: "
        + str(
            authorize_calls
        )
    )

    # =====================================================
    # 7. VERIFY DIVERSITY LOGIC
    # =====================================================

    required_logic = (
        "used_identities",
        "previous_identity",
        "semantic_query_diverse",
        "rotating_stage_fallback",
        "master_candidate_count",
        "master_semantic_rejections",
        "master_duplicate_avoidance_events",
        "master_query_count",
    )

    for marker in required_logic:

        if marker not in pipeline:

            raise RuntimeError(
                "Missing diversity logic: "
                + marker
            )

    print(
        "[PASS] Diversity-selection logic present."
    )

    # =====================================================
    # 8. BLOCK 5 MUST REMAIN
    # =====================================================

    block5_markers = (
        "BLOCK5_VISUAL_QA_BEGIN",
        "BLOCK5_VISUAL_QA_END",
        "Visual diversity gate rejected sequence",
    )

    for marker in block5_markers:

        if marker not in pipeline:

            raise RuntimeError(
                "Block 5 regression: "
                + marker
            )

    print(
        "[PASS] Independent Block 5 QA preserved."
    )

    # =====================================================
    # 9. RESEARCH STRUCTURE
    # =====================================================

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
                "Research marker missing: "
                + marker
            )

    print(
        "[PASS] Research specificity preserved."
    )

    # =====================================================
    # 10. NO DUPLICATE MASTER METHOD DEFINITIONS
    # =====================================================

    helper_names = {
        "_master_asset_identity",
        "_master_query_tokens",
        "_master_query_variants",
        "_master_metadata_score",
        "_master_choose_asset",
    }

    counts = {
        name: 0
        for name in helper_names
    }

    for node in pipeline_class.body:

        if isinstance(
            node,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
            ),
        ):

            if node.name in counts:
                counts[
                    node.name
                ] += 1

    duplicates = {
        name: count
        for name, count
        in counts.items()
        if count != 1
    }

    if duplicates:

        raise RuntimeError(
            "Master helper definition count "
            "invalid: "
            + repr(
                duplicates
            )
        )

    print(
        "[PASS] No duplicate master helper definitions."
    )

    # =====================================================
    # 11. VERIFY RE IMPORT
    # =====================================================

    has_re = any(
        isinstance(
            node,
            ast.Import,
        )
        and any(
            alias.name == "re"
            for alias in node.names
        )
        for node in pipeline_tree.body
    )

    if not has_re:

        raise RuntimeError(
            "Required re import missing."
        )

    print(
        "[PASS] Required imports present."
    )

    print("")
    print(
        "========================================================"
    )

    print(
        " MASTER VISUAL V3 STRUCTURAL VERIFICATION PASSED"
    )

    print(
        "========================================================"
    )

except Exception as exc:

    restore()

    print(
        "[ROLLBACK] Structural verification failed."
    )

    print(
        f"[ROLLBACK] {type(exc).__name__}: {exc}"
    )

    print(
        "[PASS] Original source restored."
    )

    sys.exit(3)
