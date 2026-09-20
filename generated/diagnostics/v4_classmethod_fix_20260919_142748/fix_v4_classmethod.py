from pathlib import Path
import ast
import shutil
import sys

PIPELINE = Path("backend/services/pipelines/video_pipeline.py")
BACKUP = Path(sys.argv[1]) / "video_pipeline.py"

source = PIPELINE.read_text(encoding="utf-8-sig")

try:
    tree = ast.parse(source)

    cls = next(
        (
            node for node in tree.body
            if isinstance(node, ast.ClassDef)
            and node.name == "VideoPipeline"
        ),
        None,
    )

    if cls is None:
        raise RuntimeError("VideoPipeline class not found.")

    targets = {
        "_master_query_variants",
        "_master_metadata_score",
        "_master_choose_asset",
    }

    methods = {
        node.name: node
        for node in cls.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }

    for name in targets:
        if name not in methods:
            raise RuntimeError(f"Missing V4 helper: {name}")

    lines = source.splitlines(keepends=True)
    removals = []

    for name in targets:
        node = methods[name]

        decorators = [
            decorator
            for decorator in node.decorator_list
            if isinstance(decorator, ast.Name)
            and decorator.id == "classmethod"
        ]

        if len(decorators) > 1:
            raise RuntimeError(
                f"{name} has duplicate @classmethod decorators."
            )

        if len(decorators) == 0:
            method_line = node.lineno - 1
            indent = lines[method_line][
                :len(lines[method_line]) - len(lines[method_line].lstrip())
            ]
            lines.insert(method_line, indent + "@classmethod\n")

    repaired = "".join(lines)

    # Reparse after decorator normalization.
    tree = ast.parse(repaired)

    cls = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef)
        and node.name == "VideoPipeline"
    )

    # Detect the exact bug that caused:
    # TypeError: 'classmethod' object is not callable
    #
    # This happens when a helper body was accidentally wrapped with
    # `classmethod(...)` or when a classmethod descriptor was assigned
    # inside the class instead of being used as a decorator.

    suspicious_assignments = []

    for node in cls.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue

        value = getattr(node, "value", None)

        if (
            isinstance(value, ast.Call)
            and isinstance(value.func, ast.Name)
            and value.func.id == "classmethod"
        ):
            suspicious_assignments.append(node)

    if suspicious_assignments:
        raise RuntimeError(
            "Unexpected classmethod(...) assignment exists in VideoPipeline."
        )

    # Ensure each helper is a real function with exactly one decorator.
    methods = {
        node.name: node
        for node in cls.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }

    for name in targets:
        node = methods[name]

        count = sum(
            1
            for decorator in node.decorator_list
            if isinstance(decorator, ast.Name)
            and decorator.id == "classmethod"
        )

        if count != 1:
            raise RuntimeError(
                f"{name} @classmethod count={count}"
            )

    # Critical V4 features must remain.
    required = (
        "SEMANTIC_VISUAL_V4 = True",
        "Foley artist recording movie sound effects",
        "Foley artist recording footsteps studio",
        "film sound editor post production studio",
        "negative_tokens",
        "domain_tokens",
        "semantic_rotating_stage_fallback",
        "self.asset_collector.authorize",
        "BLOCK5_VISUAL_QA_BEGIN",
        "BLOCK5_VISUAL_QA_END",
    )

    for marker in required:
        if marker not in repaired:
            raise RuntimeError(
                "Required V4 feature missing: " + marker
            )

    ast.parse(repaired)

    PIPELINE.write_text(
        repaired,
        encoding="utf-8",
    )

    print("[PASS] V4 classmethod structure repaired.")
    print("[PASS] Exactly one @classmethod on each V4 helper.")
    print("[PASS] V4 semantic visual logic preserved.")
    print("[PASS] Rights authorization preserved.")
    print("[PASS] Block 5 preserved.")

except Exception as exc:
    shutil.copy2(BACKUP, PIPELINE)

    print(
        f"[ROLLBACK] {type(exc).__name__}: {exc}"
    )
    print("[PASS] Pre-fix V4 source restored.")

    sys.exit(2)
