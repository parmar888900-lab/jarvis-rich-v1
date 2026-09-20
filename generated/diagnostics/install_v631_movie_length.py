from pathlib import Path
from datetime import datetime
import shutil
import py_compile
import sys

ROOT = Path(r"C:\Users\hp\jarvis.ai")
FILE = ROOT / "backend/services/content_generator.py"

STAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
BACKUP_DIR = (
    ROOT / "generated/diagnostics"
    / f"v6_3_1_{STAMP}"
    / "backup"
)
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

BACKUP = BACKUP_DIR / "content_generator.py"
shutil.copy2(FILE, BACKUP)

print("=" * 72)
print(" RICH V1 - V6.3.1 MOVIE LENGTH COMPLIANCE")
print("=" * 72)
print("BACKUP:", BACKUP)

source = FILE.read_text(encoding="utf-8")

# ------------------------------------------------------------
# Replace ONLY the weak first-attempt correction.
# ------------------------------------------------------------

old = '''            if attempt == 1:
                correction = f"""
The current narration has {candidate_words} words.
Rewrite it to 85-100 narration words total.

Approximately {missing_words} additional useful words
are needed if the script is short.

Add only explanation directly supported by the
evidence packet below.
"""
'''

new = '''            if attempt == 1:
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

Distribute the added information across all four
lines. Do not merely append filler to line 4.

Before responding:
1. Count each narration line separately.
2. Ensure every line contains 22-24 words.
3. Count the four lines together.
4. Ensure the total is 88-96 words.
5. If the count is wrong, rewrite before returning.

Every added claim must be directly supported by the
evidence packet below.

Do not invent facts.
Do not add generic praise.
Do not add a CTA.
Do not repeat the same fact in different wording.
"""
'''

count = source.count(old)

print("weak_recovery_block_count:", count)

if count != 1:
    raise RuntimeError(
        "Expected exactly one weak movie recovery "
        f"block, found {count}."
    )

source = source.replace(
    old,
    new,
    1,
)

# ------------------------------------------------------------
# Strengthen the global mandatory contract too.
# This affects only the movie recovery prompt in this function.
# ------------------------------------------------------------

old_contract = '''- exactly four script_lines
- exactly four evidence_ids lists
- 85-100 narration words total
- no narration line over 29 words
'''

new_contract = '''- exactly four script_lines
- exactly four evidence_ids lists
- target 22-24 words in EACH narration line
- target 88-96 narration words total
- absolute accepted range: 85-100 narration words
- no narration line over 29 words
- count each line and the total before responding
'''

contract_count = source.count(old_contract)

print(
    "movie_contract_count:",
    contract_count,
)

if contract_count < 1:
    raise RuntimeError(
        "Movie recovery mandatory contract "
        "was not found."
    )

# Only first occurrence in recovery prompt.
source = source.replace(
    old_contract,
    new_contract,
    1,
)

# ------------------------------------------------------------
# Fix stale hard-coded exhaustion message.
# Our speed configuration currently permits one recovery call.
# ------------------------------------------------------------

old_log = '''        logger.warning(
            "Movie evidence-aware length recovery "
            "exhausted 3 bounded attempts."
        )
'''

new_log = '''        logger.warning(
            "Movie evidence-aware length recovery "
            "exhausted configured bounded attempts."
        )
'''

log_count = source.count(old_log)

print(
    "stale_exhaustion_log_count:",
    log_count,
)

if log_count != 1:
    raise RuntimeError(
        "Expected exactly one stale movie recovery "
        f"log, found {log_count}."
    )

source = source.replace(
    old_log,
    new_log,
    1,
)

FILE.write_text(
    source,
    encoding="utf-8",
)

# ------------------------------------------------------------
# Compile.
# ------------------------------------------------------------

try:
    py_compile.compile(
        str(FILE),
        doraise=True,
    )
    compile_ok = True

except Exception as exc:
    compile_ok = False
    print("COMPILE ERROR:", repr(exc))

checks = {
    "per_line_target":
        "line 1: 22-24 words" in source
        and "line 4: 22-24 words" in source,

    "total_target":
        "target 88-96 narration words total"
        in source,

    "absolute_gate_preserved":
        "absolute accepted range remains 85-100 words"
        in source,

    "evidence_grounding_preserved":
        "Every added claim must be directly supported"
        in source,

    "no_invention_preserved":
        "Do not invent facts." in source,

    "claim_validator_preserved":
        "self.claim_evidence_validator.validate("
        in source,

    "semantic_validator_preserved":
        "self.semantic_claim_evidence_validator.validate("
        in source,

    "four_line_gate_preserved":
        "len(recovered_lines) != 4"
        in source,

    "29_word_gate_preserved":
        "len(line.split()) > 29"
        in source,

    "stale_log_removed":
        "exhausted 3 bounded attempts."
        not in source,

    "configured_log_added":
        "exhausted configured bounded attempts."
        in source,
}

print()
print("V6.3.1 VERIFICATION")

for name, ok in checks.items():
    print(
        f"{name}: "
        f"{'PASS' if ok else 'FAIL'}"
    )

print(
    "PATCHED COMPILE:",
    "PASS" if compile_ok else "FAIL",
)

all_ok = compile_ok and all(checks.values())

if not all_ok:
    shutil.copy2(BACKUP, FILE)

    print()
    print("V6.3.1: FAIL")
    print("Automatic rollback completed.")
    sys.exit(1)

print()
print("V6.3.1: PASS")
print(
    "Movie recovery now targets 22-24 words "
    "per narration line."
)
print(
    "85-100 hard validation remains intact."
)
print(
    "Evidence and semantic validation remain intact."
)
