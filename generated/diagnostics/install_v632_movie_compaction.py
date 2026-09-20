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
    / f"v6_3_2_{STAMP}"
    / "backup"
)
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

BACKUP = BACKUP_DIR / "content_generator.py"
shutil.copy2(FILE, BACKUP)

print("=" * 72)
print(" RICH V1 - V6.3.2 MOVIE OVERSHOOT COMPACTION")
print("=" * 72)
print("BACKUP:", BACKUP)

source = FILE.read_text(encoding="utf-8")

marker = "# RICH_V1_MOVIE_LENGTH_COMPACTION_V6_3_2"

if marker in source:
    raise RuntimeError(
        "V6.3.2 already appears to be installed."
    )

func_start = source.index(
    "    async def _recover_movie_generation_length("
)

func_end = source.index(
    "    async def _repair_movie_semantic_failures(",
    func_start,
)

func = source[func_start:func_end]

# ------------------------------------------------------------
# Exact behavioral block verified from current source.
# ------------------------------------------------------------

old = '''            if not (
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

count = func.count(old)

print(
    "length_gate_anchor_count:",
    count,
)

if count != 1:
    raise RuntimeError(
        "Expected exactly one movie recovery length "
        f"gate, found {count}."
    )

new = '''            # RICH_V1_MOVIE_LENGTH_COMPACTION_V6_3_2
            #
            # qwen2.5 can obey grounding while overshooting the
            # requested word count. Preserve the grounded candidate
            # and perform one bounded compaction pass instead of
            # discarding it immediately.
            if recovered_words > self.MAX_WORDS:
                logger.warning(
                    "Movie recovery attempt %s overshot "
                    "length at %s words. Attempting one "
                    "grounded compaction pass.",
                    attempt,
                    recovered_words,
                )

                overshoot_json = json.dumps(
                    recovered,
                    indent=2,
                )

                compact_messages = [
                    {
                        "role": "system",
                        "content": f"""
You are compacting an already-grounded movie
YouTube Short.

Return ONLY one JSON object with these keys:
"title"
"hashtags"
"script_lines"
"evidence_ids"

This is COMPACTION, not new writing.

MANDATORY:
- preserve exactly four script_lines
- preserve exactly four evidence_ids lists
- preserve the existing evidence IDs for each line
- use ONLY these legal evidence IDs:
  {allowed_evidence_text}
- do not introduce any new factual claim
- do not introduce any new evidence ID
- remove repetition, excess modifiers, and
  unnecessary wording
- target 21-24 words per narration line
- target 88-96 narration words total
- absolute accepted range is 85-100 words
- no line may exceed 29 words
- preserve the original hook -> context ->
  mechanism -> payoff progression
- no CTA
- no filler
- evidence labels must never appear in narration

Count the narration words before returning.
If the total is above 100 or below 85,
compact/rewrite again before responding.
""",
                    },
                    {
                        "role": "user",
                        "content": f"""
MOVIE:
{movie_title}

TOPIC:
{topic}

CURRENT GROUNDED OVERSHOOT:
{overshoot_json}

GROUNDED EVIDENCE PACKET:
{evidence_packet}

Shorten the existing grounded narration only.

Do not add facts.

Return JSON only.
""",
                    },
                ]

                compact_raw = await self.llm.chat(
                    compact_messages,
                    json_mode=True,
                )

                compacted = self._extract_json(
                    compact_raw
                )

                if isinstance(compacted, dict):
                    compact_words = self._word_count(
                        compacted
                    )

                    if (
                        self.MIN_WORDS
                        <= compact_words
                        <= self.MAX_WORDS
                    ):
                        recovered = compacted
                        recovered_words = compact_words

                        logger.info(
                            "Movie grounded compaction "
                            "produced %s words.",
                            recovered_words,
                        )

                    else:
                        logger.warning(
                            "Movie grounded compaction "
                            "failed length validation: "
                            "%s words.",
                            compact_words,
                        )

                else:
                    logger.warning(
                        "Movie grounded compaction "
                        "returned invalid JSON."
                    )

            if not (
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

func = func.replace(
    old,
    new,
    1,
)

patched = (
    source[:func_start]
    + func
    + source[func_end:]
)

FILE.write_text(
    patched,
    encoding="utf-8",
)

# ------------------------------------------------------------
# Compile
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
# Verify preservation of downstream gates.
# ------------------------------------------------------------

fresh = FILE.read_text(
    encoding="utf-8"
)

fresh_start = fresh.index(
    "    async def _recover_movie_generation_length("
)

fresh_end = fresh.index(
    "    async def _repair_movie_semantic_failures(",
    fresh_start,
)

fresh_func = fresh[
    fresh_start:fresh_end
]

checks = {
    "v632_marker":
        marker in fresh_func,

    "overshoot_only":
        "recovered_words > self.MAX_WORDS"
        in fresh_func,

    "single_compaction_call":
        fresh_func.count(
            "compact_raw = await self.llm.chat("
        ) == 1,

    "hard_length_gate_preserved":
        (
            "self.MIN_WORDS"
            in fresh_func
            and "self.MAX_WORDS"
            in fresh_func
        ),

    "four_lines_preserved":
        "len(recovered_lines) != 4"
        in fresh_func,

    "29_word_gate_preserved":
        "len(line.split()) > 29"
        in fresh_func,

    "evidence_structure_preserved":
        "len(raw_ids) != 4"
        in fresh_func,

    "allowed_evidence_preserved":
        "allowed_evidence_set"
        in fresh_func,

    "claim_evidence_validator_preserved":
        "self.claim_evidence_validator.validate("
        in fresh_func,

    "evidence_leakage_gate_preserved":
        'r"\\[E\\d+\\]"'
        in fresh_func,

    "one_recovery_attempt_preserved":
        "for attempt in range(1, 2):"
        in fresh_func,
}

print()
print("V6.3.2 VERIFICATION")

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
    print("V6.3.2: FAIL")
    print("Automatic rollback completed.")
    sys.exit(1)

print()
print("V6.3.2: PASS")
print(
    "Grounded recovery overshoots now receive "
    "one bounded compaction pass."
)
print(
    "All existing evidence and structural gates "
    "remain downstream and fail-closed."
)
