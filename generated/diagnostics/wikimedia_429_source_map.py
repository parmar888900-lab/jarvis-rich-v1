from pathlib import Path
import ast

path = Path(
    "backend/services/video/media_sources/wikimedia.py"
)

source = path.read_text(
    encoding="utf-8-sig"
)

tree = ast.parse(source)

wanted = {
    "search_and_download",
    "_search_and_download_sync",
    "_api",
}

found = {}

for node in ast.walk(tree):

    if isinstance(
        node,
        (ast.FunctionDef, ast.AsyncFunctionDef),
    ) and node.name in wanted:

        found[node.name] = (
            node.lineno,
            node.end_lineno,
        )

print()
print("FILE:", path)
print()

for name in (
    "search_and_download",
    "_search_and_download_sync",
    "_api",
):

    if name not in found:
        print(
            f"[MISSING] {name}"
        )
        continue

    start, end = found[name]

    # Include bounded surrounding context.
    context_start = max(
        1,
        start - 15,
    )

    context_end = min(
        len(source.splitlines()),
        end + 15,
    )

    lines = source.splitlines()

    print("=" * 78)
    print(
        f"{name}: lines {start}-{end}"
    )
    print("=" * 78)

    for number in range(
        context_start,
        context_end + 1,
    ):
        print(
            f"{number:5}: "
            f"{lines[number - 1]}"
        )

    print()

print("=" * 78)
print("429 / RETRY / CACHE / RATE-LIMIT REFERENCES")
print("=" * 78)

terms = (
    "429",
    "retry",
    "Retry-After",
    "HTTPError",
    "urlopen",
    "sleep",
    "cache",
    "cooldown",
    "rate",
    "User-Agent",
)

lines = source.splitlines()

matches = 0

for number, line in enumerate(
    lines,
    start=1,
):

    if any(
        term.lower() in line.lower()
        for term in terms
    ):
        matches += 1
        print(
            f"{number:5}: {line}"
        )

if matches == 0:
    print(
        "[INFO] No existing retry/rate-limit "
        "handling detected."
    )

print()
print("=" * 78)
print("IMPORTS")
print("=" * 78)

for node in tree.body:

    if isinstance(
        node,
        (ast.Import, ast.ImportFrom),
    ):
        segment = ast.get_source_segment(
            source,
            node,
        )

        if segment:
            print(segment)

print()
print("=" * 78)
print("SOURCE MAP COMPLETE")
print("=" * 78)
print("[PASS] Python syntax parsed.")
print("[PASS] No source changes.")
print("[PASS] No network request.")
print("[PASS] No generation.")
print("[PASS] No render.")
print("[PASS] No upload.")
print("[PASS] No restart.")
