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
    / f"v6_3_3_{STAMP}"
    / "backup"
)
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

BACKUP = BACKUP_DIR / "content_generator.py"
shutil.copy2(FILE, BACKUP)

print("=" * 72)
print(" RICH V1 - V6.3.3 BIDIRECTIONAL LENGTH NORMALIZATION")
print("=" * 72)
print("BACKUP:", BACKUP)

source = FILE.read_text(encoding="utf-8")

OLD_MARKER = "# RICH_V1_MOVIE_LENGTH_COMPACTION_V6_3_2"
NEW_MARKER = "# RICH_V1_MOVIE_LENGTH_NORMALIZATION_V6_3_3"

if NEW_MARKER in source:
    raise RuntimeError(
        "V6.3.3 already appears to be installed."
    )

if OLD_MARKER not in source:
    raise RuntimeError(
        "V6.3.2 marker not found. "
        "Refusing to patch an unexpected source state."
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
# Locate V6.3.2 normalization region structurally.
# ------------------------------------------------------------

region_start = func.index(
    "            # RICH_V1_MOVIE_LENGTH_COMPACTION_V6_3_2"
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

print(
    "v632_region_chars:",
    len(old_region),
)

if "recovered_words > self.MAX_WORDS" not in old_region:
    raise RuntimeError(
        "Expected V6.3.2 overshoot branch not found."
    )

if "compact_raw = await self.llm.chat(" not in old_region:
    raise RuntimeError(
        "Expected V6.3.2 LLM normalization call not found."
    )

# ------------------------------------------------------------
# Replace overshoot-only pass with bidirectional normalization.
# ------------------------------------------------------------

new_region = '''            # RICH_V1_MOVIE_LENGTH_NORMALIZATION_V6_3_3
            #
            # Local models can undershoot or overshoot strict word
            # targets even when grounding is correct. Perform ONE
            # bounded normalization pass whenever the recovered
            # candidate is outside 85-100 words.
            #
            # Every existing structural/evidence validator remains
            # downstream and fail-closed.
            if not (
                self.MIN_WORDS
                <= recovered_words
                <= self.MAX_WORDS
            ):
                if recovered_words < self.MIN_WORDS:
                    normalization_mode = "EXPAND"
                    normalization_instruction = f"""
The grounded narration is too short at
{recovered_words} words.

EXPAND the existing narration using ONLY details
supported by the evidence packet.

Add useful explanation across all four lines.
Do not pad with filler.
Do not invent a new claim.
"""
                else:
                    normalization_mode = "COMPACT"
                    normalization_instruction = f"""
The grounded narration is too long at
{recovered_words} words.

COMPACT the existing narration.

Remove repetition, unnecessary modifiers, and
nonessential wording.
Do not remove the core supported explanation.
Do not introduce a new claim.
"""

                logger.warning(
                    "Movie recovery attempt %s is outside "
                    "length range at %s words. Running one "
                    "grounded %s normalization pass.",
                    attempt,
                    recovered_words,
                    normalization_mode.lower(),
                )

                normalization_json = json.dumps(
                    recovered,
                    indent=2,
                )

                normalization_messages = [
                    {
                        "role": "system",
                        "content": f"""
You are performing deterministic length
normalization on an already-grounded movie
YouTube Short.

Return ONLY one JSON object with these keys:
"title"
"hashtags"
"script_lines"
"evidence_ids"

MODE:
{normalization_mode}

{normalization_instruction}

HARD OUTPUT CONTRACT:
- exactly four script_lines
- exactly four evidence_ids lists
- target exactly 22 words per narration line
- acceptable per-line range: 21-24 words
- target approximately 88 narration words total
- absolute accepted total: 85-100 words
- no narration line over 29 words
- preserve hook -> context -> mechanism -> payoff
- preserve the meaning of the grounded candidate
- every line must remain grounded
- preserve valid evidence IDs where applicable
- use ONLY legal evidence IDs from this list:
  {allowed_evidence_text}
- never invent another evidence ID
- never place evidence labels inside narration
- no CTA
- no filler
- no unsupported facts

IMPORTANT:
Aim for 22 words on EACH line rather than trying
to estimate only the total.

Before returning JSON, internally verify:
line 1 = 21-24 words
line 2 = 21-24 words
line 3 = 21-24 words
line 4 = 21-24 words
total = 85-100 words

If the count is outside those limits, revise it
before returning.
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
{normalization_json}

GROUNDED EVIDENCE PACKET:
{evidence_packet}

Perform {normalization_mode} normalization only.

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

                if isinstance(normalized, dict):
                    normalized_words = self._word_count(
                        normalized
                    )

                    logger.info(
                        "Movie grounded %s normalization "
                        "produced %s words.",
                        normalization_mode.lower(),
                        normalized_words,
                    )

                    # Use the normalized candidate only when
                    # it actually satisfies the hard length gate.
                    # Otherwise retain the original candidate and
                    # let the unchanged fail-closed gate reject it.
                    if (
                        self.MIN_WORDS
                        <= normalized_words
                        <= self.MAX_WORDS
                    ):
                        recovered = normalized
                        recovered_words = normalized_words

                else:
                    logger.warning(
                        "Movie grounded %s normalization "
                        "returned invalid JSON.",
                        normalization_mode.lower(),
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
    print(
        "COMPILE ERROR:",
        repr(exc),
    )

# ------------------------------------------------------------
# Verify.
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
    "v633_marker":
        NEW_MARKER in fresh_func,

    "v632_marker_removed":
        OLD_MARKER not in fresh_func,

    "undershoot_supported":
        "recovered_words < self.MIN_WORDS"
        in fresh_func,

    "expand_mode":
        'normalization_mode = "EXPAND"'
        in fresh_func,

    "compact_mode":
        'normalization_mode = "COMPACT"'
        in fresh_func,

    "one_normalization_call":
        fresh_func.count(
            "normalization_raw = await self.llm.chat("
        ) == 1,

    "hard_85_100_gate":
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

    "claim_validator":
        "self.claim_evidence_validator.validate("
        in fresh_func,

    "label_leakage_gate":
        'r"\\[E\\d+\\]"'
        in fresh_func,

    "one_primary_recovery":
        "for attempt in range(1, 2):"
        in fresh_func,
}

print()
print("V6.3.3 VERIFICATION")

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
    shutil.copy2(
        BACKUP,
        FILE,
    )

    print()
    print("V6.3.3: FAIL")
    print("Automatic rollback completed.")
    sys.exit(1)

print()
print("V6.3.3: PASS")
print(
    "Short grounded recovery -> one EXPAND pass."
)
print(
    "Long grounded recovery -> one COMPACT pass."
)
print(
    "85-100 -> accepted without normalization."
)
print(
    "All downstream evidence/structure gates remain intact."
)
