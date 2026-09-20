from pathlib import Path
import ast
import shutil
import sys

PIPELINE = Path("backend/services/pipelines/video_pipeline.py")
BACKUP = Path(sys.argv[1]) / "video_pipeline.py"

TARGETS = {
    "_master_query_variants",
    "_master_metadata_score",
    "_master_choose_asset",
}

try:
    source = PIPELINE.read_text(encoding="utf-8-sig")
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

    methods = {
        node.name: node
        for node in cls.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }

    for name in TARGETS:
        if name not in methods:
            raise RuntimeError(f"Missing V4 helper: {name}")

    lines = source.splitlines(keepends=True)

    # Remove ALL existing @classmethod decorators attached to the
    # three V4 helpers, then insert exactly one. This directly fixes
    # the descriptor-within-descriptor failure.
    operations = []

    for name in TARGETS:
        node = methods[name]

        decorator_lines = []

        for decorator in node.decorator_list:
            if (
                isinstance(decorator, ast.Name)
                and decorator.id == "classmethod"
            ):
                decorator_lines.append(decorator.lineno - 1)

        operations.append(
            (
                node.lineno - 1,
                decorator_lines,
                name,
            )
        )

    # Work bottom-up so line numbers remain stable.
    for method_index, decorator_lines, name in sorted(
        operations,
        key=lambda item: item[0],
        reverse=True,
    ):
        for line_index in sorted(decorator_lines, reverse=True):
            del lines[line_index]

            if line_index < method_index:
                method_index -= 1

        method_line = lines[method_index]

        indent = method_line[
            :len(method_line) - len(method_line.lstrip())
        ]

        lines.insert(
            method_index,
            indent + "@classmethod\n",
        )

    repaired = "".join(lines)

    tree = ast.parse(repaired)

    cls = next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef)
        and node.name == "VideoPipeline"
    )

    methods = {
        node.name: node
        for node in cls.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }

    for name in TARGETS:
        node = methods[name]

        classmethod_count = sum(
            1
            for decorator in node.decorator_list
            if isinstance(decorator, ast.Name)
            and decorator.id == "classmethod"
        )

        if classmethod_count != 1:
            raise RuntimeError(
                f"{name}: expected 1 @classmethod, "
                f"found {classmethod_count}"
            )

        if len(node.decorator_list) != 1:
            other = [
                ast.unparse(d)
                for d in node.decorator_list
                if not (
                    isinstance(d, ast.Name)
                    and d.id == "classmethod"
                )
            ]

            if other:
                raise RuntimeError(
                    f"{name}: unexpected decorators: {other}"
                )

    required = (
        "SEMANTIC_VISUAL_V4 = True",
        "MASTER_VISUAL_ACQUISITION_V2",
        "Foley artist recording movie sound effects",
        "Foley artist recording footsteps studio",
        "film sound editor post production studio",
        "negative_tokens",
        "domain_tokens",
        "semantic_rotating_stage_fallback",
        "used_identities",
        "previous_identity",
        "self.asset_collector.authorize",
        "BLOCK5_VISUAL_QA_BEGIN",
        "BLOCK5_VISUAL_QA_END",
    )

    for marker in required:
        if marker not in repaired:
            raise RuntimeError(
                "Required feature missing after repair: "
                + marker
            )

    ast.parse(repaired)

    PIPELINE.write_text(
        repaired,
        encoding="utf-8",
    )

    print("[PASS] Removed duplicate V4 classmethod decorators.")
    print("[PASS] _master_query_variants has exactly one @classmethod.")
    print("[PASS] _master_metadata_score has exactly one @classmethod.")
    print("[PASS] _master_choose_asset has exactly one @classmethod.")
    print("[PASS] V4 semantic logic preserved.")
    print("[PASS] Rights authorization preserved.")
    print("[PASS] Block 5 preserved.")

except Exception as exc:
    shutil.copy2(BACKUP, PIPELINE)

    print(
        f"[ROLLBACK] {type(exc).__name__}: {exc}"
    )
    print("[PASS] Source restored.")

    sys.exit(2)
