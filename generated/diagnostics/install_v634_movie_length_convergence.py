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
    / f"v6_3_4_{STAMP}"
    / "backup"
)
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

BACKUP = BACKUP_DIR / "content_generator.py"
shutil.copy2(FILE, BACKUP)

print("=" * 72)
print(" RICH V1 - V6.3.4 MOVIE LENGTH CONVERGENCE")
print("=" * 72)
print("BACKUP:", BACKUP)

source = FILE.read_text(encoding="utf-8")

OLD_MARKER = "# RICH_V1_MOVIE_LENGTH_NORMALIZATION_V6_3_3"
NEW_MARKER = "# RICH_V1_MOVIE_LENGTH_CONVERGENCE_V6_3_4"

if NEW_MARKER in source:
    raise RuntimeError(
        "V6.3.4 already appears installed."
    )

if OLD_MARKER not in source:
    raise RuntimeError(
        "V6.3.3 marker not found. "
        "Refusing to modify unexpected source."
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
# Find V6.3.3 region.
# ------------------------------------------------------------

region_start = func.index(
    "            # RICH_V1_MOVIE_LENGTH_NORMALIZATION_V6_3_3"
)

final_gate = '''            if not (
                self.MIN_WORDS
                <= recovered_words
                <= self.MAX_WORDS
            ):
                logger.warning(
                    "Movie recovery attempt %s "
                    "failed length validation: %s words.",
                    attempt,
                    recovered_words,
                )

                current_candidate = recovered
                continue

            recovered_lines = [
'''

region_end = func.index(
    final_gate,
    region_start,
)

old_region = func[region_start:region_end]

print("old_v633_region_chars:", len(old_region))

required_old_tokens = [
    'normalization_mode = "EXPAND"',
    'normalization_mode = "COMPACT"',
    "normalization_raw = await self.llm.chat(",
]

for token in required_old_tokens:
    if token not in old_region:
        raise RuntimeError(
            f"Expected V6.3.3 token missing: {token}"
        )

# ------------------------------------------------------------
# Replace one-shot normalization with bounded convergence.
# ------------------------------------------------------------

new_region = '''            # RICH_V1_MOVIE_LENGTH_CONVERGENCE_V6_3_4
            #
            # Word-count compliance is treated as a measured
            # convergence problem, not a one-shot prompt problem.
            #
            # Up to four bounded normalization passes are allowed.
            # Each pass measures the ACTUAL returned word count and
            # chooses EXPAND or COMPACT for the next pass.
            #
            # No candidate bypasses the unchanged structural,
            # evidence-ID, claim-evidence, or leakage validators
            # below.
            if not (
                self.MIN_WORDS
                <= recovered_words
                <= self.MAX_WORDS
            ):
                normalization_candidate = recovered

                for normalization_attempt in range(1, 5):
                    normalization_words = self._word_count(
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

                    if normalization_words < self.MIN_WORDS:
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

                    logger.warning(
                        "Movie length convergence pass %s/4: "
                        "%s words -> %s toward 90.",
                        normalization_attempt,
                        normalization_words,
                        normalization_mode.lower(),
                    )

                    candidate_json = json.dumps(
                        normalization_candidate,
                        indent=2,
                    )

                    normalization_messages = [
                        {
                            "role": "system",
                            "content": f"""
You are a precision length editor for a grounded
movie YouTube Short.

Your ONLY job is to move an existing grounded
script toward the required narration length.

MODE:
{normalization_mode}

{mode_instruction}

RETURN ONLY ONE JSON OBJECT.

Required keys:
"title"
"hashtags"
"script_lines"
"evidence_ids"

NON-NEGOTIABLE STRUCTURE:
- exactly four script_lines
- exactly four evidence_ids lists
- keep the same four-part story progression:
  1. hook
  2. context
  3. mechanism / strongest explanation
  4. payoff

LENGTH:
- TARGET TOTAL: 90 narration words
- ACCEPTABLE TOTAL: 85-100 narration words
- ideal line length: 21-24 words
- absolute maximum per line: 29 words

GROUNDING:
- use ONLY facts supported by the evidence packet
- use ONLY these legal evidence IDs:
  {allowed_evidence_text}
- every line must retain at least one legal
  evidence ID
- never invent an evidence ID
- never invent a factual claim
- never put evidence labels inside narration

STYLE:
- natural spoken narration
- no CTA
- no filler
- no repeated fact
- no generic praise
- no meta commentary

IMPORTANT:
The ACTUAL measured word count from Python is
{normalization_words}.

Do not trust the previous prompt's estimate.
Edit specifically from {normalization_words}
toward 90 words.

Return JSON only.
""",
                        },
                        {
                            "role": "user",
                            "content": f"""
MOVIE:
{movie_title}

TOPIC:
{topic}

CURRENT GROUNDED SCRIPT:
{candidate_json}

GROUNDED EVIDENCE PACKET:
{evidence_packet}

Perform the requested {normalization_mode}
operation.

Return JSON only.
""",
                        },
                    ]

                    normalization_raw = await self.llm.chat(
                        normalization_messages,
                        json_mode=True,
                    )

                    normalized = self._extract_json(
                        normalization_raw
                    )

                    if not isinstance(normalized, dict):
                        logger.warning(
                            "Movie length convergence pass %s "
                            "returned invalid JSON.",
                            normalization_attempt,
                        )
                        continue

                    if not self._is_structurally_valid_content(
                        normalized
                    ):
                        logger.warning(
                            "Movie length convergence pass %s "
                            "returned structurally invalid content.",
                            normalization_attempt,
                        )
                        continue

                    new_words = self._word_count(
                        normalized
                    )

                    logger.warning(
                        "Movie length convergence pass %s "
                        "result: %s -> %s words.",
                        normalization_attempt,
                        normalization_words,
                        new_words,
                    )

                    normalization_candidate = normalized

                    if (
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

                else:
                    # Preserve final candidate for diagnostics,
                    # but the unchanged hard gate below will reject
                    # it if it remains outside 85-100.
                    recovered = normalization_candidate
                    recovered_words = self._word_count(
                        normalization_candidate
                    )

'''

func = (
    func[:region_start]
    + new_region
    + func[region_end:]
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

# ------------------------------------------------------------
# Verify the exact safety/quality properties.
# ------------------------------------------------------------

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
    "v634_marker":
        NEW_MARKER in fresh_func,

    "v633_removed":
        OLD_MARKER not in fresh_func,

    "four_pass_bound":
        "for normalization_attempt in range(1, 5):"
        in fresh_func,

    "measures_each_candidate":
        "normalization_words = self._word_count("
        in fresh_func,

    "measures_each_result":
        "new_words = self._word_count("
        in fresh_func,

    "expand_direction":
        'normalization_mode = "EXPAND"'
        in fresh_func,

    "compact_direction":
        'normalization_mode = "COMPACT"'
        in fresh_func,

    "target_90":
        "90 - normalization_words"
        in fresh_func
        and "normalization_words - 90"
        in fresh_func,

    "hard_length_gate":
        (
            "self.MIN_WORDS"
            in fresh_func
            and "self.MAX_WORDS"
            in fresh_func
        ),

    "four_line_gate":
        "len(recovered_lines) != 4"
        in fresh_func,

    "29_word_gate":
        "len(line.split()) > 29"
        in fresh_func,

    "evidence_structure_gate":
        "len(raw_ids) != 4"
        in fresh_func,

    "legal_evidence_gate":
        "allowed_evidence_set"
        in fresh_func,

    "claim_evidence_validator":
        "self.claim_evidence_validator.validate("
        in fresh_func,

    "evidence_leakage_gate":
        'r"\\[E\\d+\\]"'
        in fresh_func,

    "primary_recovery_bound":
        "for attempt in range(1, 2):"
        in fresh_func,
}

print()
print("V6.3.4 VERIFICATION")

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
    print("V6.3.4: FAIL")
    print("Automatic rollback completed.")
    sys.exit(1)

print()
print("V6.3.4: PASS")
print(
    "Movie length control now uses measured bounded convergence."
)
print(
    "Maximum normalization passes: 4."
)
print(
    "Target: 90 words. Hard accepted range remains 85-100."
)
print(
    "All downstream grounding/evidence gates remain fail-closed."
)
