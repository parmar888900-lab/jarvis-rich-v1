from pathlib import Path
import ast
import shutil
import sys

pipeline = Path("backend/services/pipelines/video_pipeline.py")
backup = Path(sys.argv[1]) / "video_pipeline.py"

targets = {
    "_master_query_variants",
    "_master_metadata_score",
    "_master_choose_asset",
}

try:
    source = pipeline.read_text(encoding="utf-8-sig")
    tree = ast.parse(source)

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

    missing = targets.difference(methods)

    if missing:
        raise RuntimeError(
            "Missing V4 helpers: " + ", ".join(sorted(missing))
        )

    lines = source.splitlines(keepends=True)

    jobs = []

    for name in targets:
        node = methods[name]

        classmethod_lines = [
            decorator.lineno - 1
            for decorator in node.decorator_list
            if isinstance(decorator, ast.Name)
            and decorator.id == "classmethod"
        ]

        jobs.append(
            (
                node.lineno - 1,
                classmethod_lines,
                name,
            )
        )

    # Bottom-up keeps original AST line references valid.
    for method_index, decorator_lines, name in sorted(
        jobs,
        key=lambda item: item[0],
        reverse=True,
    ):
        for decorator_index in sorted(
            decorator_lines,
            reverse=True,
        ):
            del lines[decorator_index]

            if decorator_index < method_index:
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
                f"{name}: @classmethod count={count}"
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
        "self.asset_collector.authorize",
        "BLOCK5_VISUAL_QA_BEGIN",
        "BLOCK5_VISUAL_QA_END",
    )

    for marker in required:
        if marker not in repaired:
            raise RuntimeError(
                "Required feature missing: " + marker
            )

    pipeline.write_text(
        repaired,
        encoding="utf-8",
    )

    print("[PASS] Duplicate decorators repaired.")

    for name in sorted(targets):
        print(
            f"[PASS] {name}: exactly one @classmethod."
        )

    print("[PASS] V4 semantic logic preserved.")
    print("[PASS] Rights gate preserved.")
    print("[PASS] Block 5 preserved.")

except Exception as exc:
    shutil.copy2(backup, pipeline)

    print(
        f"[ROLLBACK] {type(exc).__name__}: {exc}"
    )
    print("[PASS] Original source restored.")

    sys.exit(2)
