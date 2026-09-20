from pathlib import Path
import py_compile
import sys

path = Path(r"backend/services/content_generator.py")
text = path.read_text(encoding="utf-8")

old = """        for attempt in range(1, 4):"""
new = """        # Rich V1 sprint: one decisive grounded recovery attempt.
        # The normal generation + regeneration have already run.
        # Keep every existing structural, length, evidence, and
        # claim-evidence validation gate below unchanged.
        for attempt in range(1, 2):"""

if old not in text:
    raise RuntimeError(
        "Expected movie recovery loop anchor was not found. "
        "Production file was not modified."
    )

if text.count(old) != 1:
    raise RuntimeError(
        f"Expected exactly one recovery-loop anchor; found {text.count(old)}. "
        "Production file was not modified."
    )

updated = text.replace(old, new, 1)
path.write_text(updated, encoding="utf-8")

try:
    py_compile.compile(str(path), doraise=True)
except Exception:
    path.write_text(text, encoding="utf-8")
    raise

print("PATCH: PASS")
print("Movie length recovery attempts: 3 -> 1")
print("All validation gates preserved.")
