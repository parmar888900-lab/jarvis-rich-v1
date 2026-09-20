from pathlib import Path
from datetime import datetime
import shutil
import py_compile
import sys
import re

ROOT = Path(r"C:\Users\hp\jarvis.ai")
FILE = ROOT / "backend/services/content_generator.py"

STAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
BACKUP_DIR = (
    ROOT / "generated/diagnostics"
    / f"v6_3_1_robust_{STAMP}"
    / "backup"
)
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

BACKUP = BACKUP_DIR / "content_generator.py"
shutil.copy2(FILE, BACKUP)

print("=" * 72)
print(" RICH V1 - V6.3.1 ROBUST MOVIE LENGTH COMPLIANCE")
print("=" * 72)
print("BACKUP:", BACKUP)

source = FILE.read_text(encoding="utf-8")

# ------------------------------------------------------------
# Guardrails
# ------------------------------------------------------------

if "async def _recover_movie_generation_length(" not in source:
    raise RuntimeError(
        "Movie recovery function not found."
    )

if "line 1: 22-24 words" in source:
    raise RuntimeError(
        "V6.3.1 appears to already be installed."
    )

# Work ONLY inside movie recovery function.
start = source.index(
    "    async def _recover_movie_generation_length("
)

end_marker = (
    "    async def _repair_movie_semantic_failures("
)

end = source.index(
    end_marker,
    start,
)

before = source[:start]
func = source[start:end]
after = source[end:]

# ------------------------------------------------------------
# Confirm current speed configuration.
# ------------------------------------------------------------

attempt_matches = re.findall(
    r"for\s+attempt\s+in\s+range\(\s*1\s*,\s*(\d+)\s*\)",
    func,
)

print(
    "recovery_range_end_values:",
    attempt_matches,
)

if not attempt_matches:
    raise RuntimeError(
        "Could not locate bounded movie recovery loop."
    )

# ------------------------------------------------------------
# Replace attempt-1 correction using structural anchors rather
# than exact whitespace.
# ------------------------------------------------------------

branch_start_token = "            if attempt == 1:"
branch_start = func.find(branch_start_token)

if branch_start < 0:
    raise RuntimeError(
        "Movie recovery attempt-1 branch not found."
    )

else_token = "\n            else:"
branch_end = func.find(
    else_token,
    branch_start,
)

if branch_end < 0:
    raise RuntimeError(
        "Movie recovery attempt-1 else boundary not found."
    )

old_branch = func[
    branch_start:branch_end
]

print(
    "attempt1_branch_chars:",
    len(old_branch),
)

if "correction = f" not in old_branch:
    raise RuntimeError(
        "Attempt-1 branch does not contain correction prompt."
    )

if "candidate_words" not in old_branch:
    raise RuntimeError(
        "Attempt-1 branch does not reference candidate_words."
    )

new_branch = '''            if attempt == 1:
                correction = f"""
The current narration has {candidate_words} words and
is too short.

Rewrite the ENTIRE narration, not just the ending.

HARD LENGTH CONTRACT:
- exactly four narration lines
- line 1: 22-24 words
- line 2: 22-24 words
- line 3: 22-24 words
- line 4: 22-24 words
- target 88-96 narration words total
- absolute accepted range remains 85-100 words
- no line may exceed 29 words

The current script needs approximately
{missing_words} additional useful words.

Distribute added information across all four lines.
Do not simply append filler to the final line.

Before responding:
1. Count each narration line separately.
2. Ensure every line contains 22-24 words.
3. Count all four narration lines together.
4. Ensure the total is 88-96 words.
5. If any count is wrong, rewrite before returning.

Every added claim must be directly supported by the
evidence packet below.

Do not invent facts.
Do not add generic praise.
Do not add a CTA.
Do not repeat the same fact in different wording.
"""'''

func = (
    func[:branch_start]
    + new_branch
    + func[branch_end:]
)

# ------------------------------------------------------------
# Strengthen mandatory recovery contract.
#
# Scope is ONLY this function.
# ------------------------------------------------------------

contract_pattern = re.compile(
    r"- exactly four script_lines\s*\n"
    r"- exactly four evidence_ids lists\s*\n"
    r"- 85-100 narration words total\s*\n"
    r"- no narration line over 29 words"
)

contract_replacement = """- exactly four script_lines
- exactly four evidence_ids lists
- target 22-24 words in EACH narration line
- target 88-96 narration words total
- absolute accepted range: 85-100 narration words
- no narration line over 29 words
- count each line and the total before responding"""

func, contract_changes = (
    contract_pattern.subn(
        contract_replacement,
        func,
        count=1,
    )
)

print(
    "mandatory_contract_changes:",
    contract_changes,
)

if contract_changes != 1:
    raise RuntimeError(
        "Could not uniquely strengthen movie "
        "recovery mandatory contract."
    )

# ------------------------------------------------------------
# Fix stale log only inside this function.
# ------------------------------------------------------------

stale = (
    '"exhausted 3 bounded attempts."'
)

replacement = (
    '"exhausted configured bounded attempts."'
)

stale_count = func.count(stale)

print(
    "stale_log_count:",
    stale_count,
)

if stale_count != 1:
    raise RuntimeError(
        "Expected one stale recovery log, "
        f"found {stale_count}."
    )

func = func.replace(
    stale,
    replacement,
    1,
)

patched = before + func + after

# ------------------------------------------------------------
# Write and compile.
# ------------------------------------------------------------

FILE.write_text(
    patched,
    encoding="utf-8",
)

try:
    py_compile.compile(
        str(FILE),
        doraise=True,
    )
    compile_ok = True

except Exception as exc:
    compile_ok = False
    print(
        "COMPILE ERROR:",
        repr(exc),
    )

# ------------------------------------------------------------
# Verify actual behavioral gates, not just comments.
# ------------------------------------------------------------

patched_func = patched[start:(
    patched.index(
        end_marker,
        start,
    )
)]

checks = {
    "per_line_22_24":
        all(
            f"line {i}: 22-24 words"
            in patched_func
            for i in range(1, 5)
        ),

    "target_88_96":
        "target 88-96 narration words total"
        in patched_func,

    "hard_85_100_validator":
        (
            "self.MIN_WORDS"
            in patched_func
            and "self.MAX_WORDS"
            in patched_func
        ),

    "29_word_validator":
        "len(line.split()) > 29"
        in patched_func,

    "four_line_validator":
        "len(recovered_lines) != 4"
        in patched_func,

    "evidence_validator":
        "self.claim_evidence_validator.validate("
        in patched_func,

    "legal_evidence_gate":
        "allowed_evidence_set"
        in patched_func,

    "no_evidence_leakage_gate":
        'r"\\[E\\d+\\]"'
        in patched_func,

    "stale_log_removed":
        "exhausted 3 bounded attempts."
        not in patched_func,

    "configured_log":
        "exhausted configured bounded attempts."
        in patched_func,
}

print()
print("V6.3.1 ROBUST VERIFICATION")

for name, ok in checks.items():
    print(
        f"{name}: "
        f"{'PASS' if ok else 'FAIL'}"
    )

print(
    "PATCHED COMPILE:",
    "PASS" if compile_ok else "FAIL",
)

all_ok = (
    compile_ok
    and all(checks.values())
)

if not all_ok:
    shutil.copy2(
        BACKUP,
        FILE,
    )

    print()
    print("V6.3.1 ROBUST: FAIL")
    print("Automatic rollback completed.")
    sys.exit(1)

print()
print("V6.3.1 ROBUST: PASS")
print(
    "Single movie recovery now explicitly targets "
    "88-96 words across four balanced lines."
)
print(
    "85-100 validation, evidence validation, and "
    "fail-closed behavior remain intact."
)
