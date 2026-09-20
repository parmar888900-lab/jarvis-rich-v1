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
    / f"v6_3_6_{STAMP}"
    / "backup"
)
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

BACKUP = BACKUP_DIR / "content_generator.py"
shutil.copy2(FILE, BACKUP)

print("=" * 72)
print(" RICH V1 - V6.3.6 STRUCTURAL LENGTH CONVERGENCE")
print("=" * 72)
print("BACKUP:", BACKUP)

source = FILE.read_text(encoding="utf-8")

MARKER_634 = "# RICH_V1_MOVIE_LENGTH_CONVERGENCE_V6_3_4"
MARKER_636 = "# RICH_V1_MOVIE_STRUCTURAL_CONVERGENCE_V6_3_6"

if MARKER_636 in source:
    raise RuntimeError("V6.3.6 already installed.")

if MARKER_634 not in source:
    raise RuntimeError(
        "V6.3.4 convergence marker missing. "
        "Refusing unexpected source state."
    )

func_start = source.index(
    "    async def _recover_movie_generation_length("
)

func_end = source.index(
    "    async def _repair_movie_semantic_failures(",
    func_start,
)

before = source[:func_start]
func = source[func_start:func_end]
after = source[func_end:]

# ------------------------------------------------------------
# 1. Upgrade marker.
# ------------------------------------------------------------

func = func.replace(
    MARKER_634,
    MARKER_636,
    1,
)

# ------------------------------------------------------------
# 2. Add structural measurement immediately after
#    normalization_words is measured.
# ------------------------------------------------------------

old_measure = '''                    normalization_words = self._word_count(
                        normalization_candidate
                    )

                    if (
                        self.MIN_WORDS
                        <= normalization_words
                        <= self.MAX_WORDS
                    ):
                        recovered = normalization_candidate
                        recovered_words = normalization_words
                        break
'''

new_measure = '''                    normalization_words = self._word_count(
                        normalization_candidate
                    )

                    normalization_lines = [
                        str(line).strip()
                        for line in normalization_candidate.get(
                            "script_lines",
                            [],
                        )
                        if str(line).strip()
                    ]

                    line_word_counts = [
                        len(line.split())
                        for line in normalization_lines
                    ]

                    structure_valid = (
                        len(normalization_lines) == 4
                        and all(
                            count <= 29
                            for count in line_word_counts
                        )
                    )

                    if (
                        self.MIN_WORDS
                        <= normalization_words
                        <= self.MAX_WORDS
                        and structure_valid
                    ):
                        recovered = normalization_candidate
                        recovered_words = normalization_words
                        break
'''

if func.count(old_measure) != 1:
    raise RuntimeError(
        "Could not locate V6.3.4 convergence measurement block."
    )

func = func.replace(
    old_measure,
    new_measure,
    1,
)

# ------------------------------------------------------------
# 3. Add REBALANCE mode before normal EXPAND/COMPACT.
# ------------------------------------------------------------

old_direction = '''                    if normalization_words < self.MIN_WORDS:
                        normalization_mode = "EXPAND"
                        word_delta = (
                            90 - normalization_words
                        )

                        mode_instruction = f"""
The current narration is TOO SHORT.

ACTUAL CURRENT WORD COUNT:
{normalization_words}

TARGET:
90 narration words.

You need approximately {word_delta} MORE words.

Expand the EXISTING supported explanation.
Add concrete detail only when supported by the
evidence packet.

Do not merely append a long ending.
Distribute useful additions across the four lines.
"""

                    else:
                        normalization_mode = "COMPACT"
                        word_delta = (
                            normalization_words - 90
                        )

                        mode_instruction = f"""
The current narration is TOO LONG.

ACTUAL CURRENT WORD COUNT:
{normalization_words}

TARGET:
90 narration words.

Remove approximately {word_delta} words.

Delete repetition, weak modifiers, redundant
phrasing, and unnecessary setup.

Preserve the supported factual meaning.
"""
'''

new_direction = '''                    if (
                        self.MIN_WORDS
                        <= normalization_words
                        <= self.MAX_WORDS
                        and not structure_valid
                    ):
                        normalization_mode = "REBALANCE"

                        mode_instruction = f"""
The TOTAL narration length is acceptable, but
the four-line structure is not.

ACTUAL TOTAL WORD COUNT:
{normalization_words}

ACTUAL LINE WORD COUNTS:
{line_word_counts}

REBALANCE the SAME grounded information across
exactly four narration lines.

HARD REQUIREMENTS:
- exactly four lines
- NO line may exceed 29 words
- target roughly 21-24 words per line
- preserve approximately the same total length
- preserve each line's cited evidence
- do not add any factual claim
- do not remove the core explanation
"""

                    elif normalization_words < self.MIN_WORDS:
                        normalization_mode = "EXPAND"
                        word_delta = (
                            90 - normalization_words
                        )

                        mode_instruction = f"""
The current narration is TOO SHORT.

ACTUAL CURRENT WORD COUNT:
{normalization_words}

TARGET:
90 narration words.

You need approximately {word_delta} MORE words.

Expand the EXISTING supported explanation.
Add concrete detail only when supported by the
evidence packet.

Do not merely append a long ending.
Distribute useful additions across the four lines.
"""

                    else:
                        normalization_mode = "COMPACT"
                        word_delta = (
                            normalization_words - 90
                        )

                        mode_instruction = f"""
The current narration is TOO LONG.

ACTUAL CURRENT WORD COUNT:
{normalization_words}

TARGET:
90 narration words.

Remove approximately {word_delta} words.

Delete repetition, weak modifiers, redundant
phrasing, and unnecessary setup.

Preserve the supported factual meaning.
"""
'''

if func.count(old_direction) != 1:
    raise RuntimeError(
        "Could not locate V6.3.4 direction block."
    )

func = func.replace(
    old_direction,
    new_direction,
    1,
)

# ------------------------------------------------------------
# 4. Fix post-LLM acceptance:
#    total range alone is no longer sufficient.
# ------------------------------------------------------------

old_accept = '''                    if (
                        self.MIN_WORDS
                        <= new_words
                        <= self.MAX_WORDS
                    ):
                        recovered = normalized
                        recovered_words = new_words

                        logger.info(
                            "Movie length convergence reached "
                            "valid range on pass %s: %s words.",
                            normalization_attempt,
                            new_words,
                        )
                        break
'''

new_accept = '''                    new_lines = [
                        str(line).strip()
                        for line in normalized.get(
                            "script_lines",
                            [],
                        )
                        if str(line).strip()
                    ]

                    new_line_word_counts = [
                        len(line.split())
                        for line in new_lines
                    ]

                    new_structure_valid = (
                        len(new_lines) == 4
                        and all(
                            count <= 29
                            for count in new_line_word_counts
                        )
                    )

                    if (
                        self.MIN_WORDS
                        <= new_words
                        <= self.MAX_WORDS
                        and new_structure_valid
                    ):
                        recovered = normalized
                        recovered_words = new_words

                        logger.info(
                            "Movie structural convergence reached "
                            "valid range on pass %s: %s words; "
                            "lines=%s.",
                            normalization_attempt,
                            new_words,
                            new_line_word_counts,
                        )
                        break

                    if (
                        self.MIN_WORDS
                        <= new_words
                        <= self.MAX_WORDS
                        and not new_structure_valid
                    ):
                        logger.warning(
                            "Movie convergence pass %s has valid "
                            "total length but invalid line structure: "
                            "%s words; lines=%s. Rebalancing.",
                            normalization_attempt,
                            new_words,
                            new_line_word_counts,
                        )
'''

if func.count(old_accept) != 1:
    raise RuntimeError(
        "Could not locate V6.3.4 post-normalization acceptance block."
    )

func = func.replace(
    old_accept,
    new_accept,
    1,
)

patched = before + func + after

FILE.write_text(
    patched,
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

fresh = FILE.read_text(encoding="utf-8")

fresh_start = fresh.index(
    "    async def _recover_movie_generation_length("
)

fresh_end = fresh.index(
    "    async def _repair_movie_semantic_failures(",
    fresh_start,
)

fresh_func = fresh[fresh_start:fresh_end]

checks = {
    "v636_marker":
        MARKER_636 in fresh_func,

    "v634_marker_replaced":
        MARKER_634 not in fresh_func,

    "four_pass_bound":
        "for normalization_attempt in range(1, 5):"
        in fresh_func,

    "four_line_measurement":
        "len(normalization_lines) == 4"
        in fresh_func,

    "29_word_convergence_gate":
        "count <= 29"
        in fresh_func,

    "rebalance_mode":
        'normalization_mode = "REBALANCE"'
        in fresh_func,

    "line_counts_given_to_model":
        "ACTUAL LINE WORD COUNTS:"
        in fresh_func,

    "post_llm_structure_check":
        "new_structure_valid"
        in fresh_func,

    "total_and_structure_required":
        "and new_structure_valid"
        in fresh_func,

    "existing_29_word_fail_closed_gate":
        "len(line.split()) > 29"
        in fresh_func,

    "claim_evidence_validation_preserved":
        "self.claim_evidence_validator.validate("
        in fresh_func,

    "one_primary_recovery":
        "for attempt in range(1, 2):"
        in fresh_func,
}

print()
print("V6.3.6 VERIFICATION")

for name, ok in checks.items():
    print(
        f"{name}: {'PASS' if ok else 'FAIL'}"
    )

print(
    "PATCHED COMPILE:",
    "PASS" if compile_ok else "FAIL",
)

all_ok = compile_ok and all(checks.values())

if not all_ok:
    shutil.copy2(BACKUP, FILE)

    print()
    print("V6.3.6: FAIL")
    print("Automatic rollback completed.")
    sys.exit(1)

print()
print("V6.3.6: PASS")
print("Convergence now requires:")
print("  - accepted total word count")
print("  - exactly four narration lines")
print("  - every line <= 29 words")
print("Oversized lines trigger REBALANCE instead of false success.")
print("Evidence validators remain unchanged.")
