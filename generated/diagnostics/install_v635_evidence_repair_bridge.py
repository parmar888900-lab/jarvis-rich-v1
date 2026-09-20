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
    / f"v6_3_5_{STAMP}"
    / "backup"
)
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

BACKUP = BACKUP_DIR / "content_generator.py"
shutil.copy2(FILE, BACKUP)

print("=" * 72)
print(" RICH V1 - V6.3.5 EVIDENCE REPAIR BRIDGE")
print("=" * 72)
print("BACKUP:", BACKUP)

source = FILE.read_text(encoding="utf-8")

MARKER = "# RICH_V1_LEXICAL_REPAIR_BRIDGE_V6_3_5"

if MARKER in source:
    raise RuntimeError(
        "V6.3.5 already appears installed."
    )

# ------------------------------------------------------------
# Replace ONLY the early movie validation block.
# ------------------------------------------------------------

old = '''        if format_name == "famous_movie_commentary":

            evidence_ids = data.get(
                "evidence_ids",
                [],
            )

            evidence_validation = (
                self.claim_evidence_validator.validate(
                    script_lines=lines,
                    evidence_ids=evidence_ids,
                    research=research,
                )
            )

            if not evidence_validation.valid:
                raise RuntimeError(
                    "Movie script failed claim-evidence validation: "
                    f"{evidence_validation.issues}"
                )

        if format_name == "famous_movie_commentary":

            semantic_validation = (
                await self.semantic_claim_evidence_validator.validate(
                    script_lines=lines,
                    evidence_ids=data.get(
                        "evidence_ids",
                        [],
                    ),
                    research=research,
                )
            )

            if not semantic_validation.valid:

                repaired_lines = (
                    await self._repair_movie_semantic_failures(
                        script_lines=lines,
                        evidence_ids=data.get(
                            "evidence_ids",
                            [],
                        ),
                        research=research,
                        semantic_validation=semantic_validation,
                        topic=topic,
                        movie_title=movie_title,
                    )
                )

                if repaired_lines is None:
                    raise RuntimeError(
                        "Movie script failed semantic evidence "
                        "validation and targeted repair failed: "
                        f"{semantic_validation.to_dict()}"
                    )

                lines = repaired_lines

                data["script_lines"] = list(
                    repaired_lines
                )

                logger.info(
                    "Targeted semantic movie repair succeeded."
                )
'''

count = source.count(old)

print("main_validation_anchor_count:", count)

if count != 1:
    raise RuntimeError(
        "Expected exactly one main movie validation block, "
        f"found {count}."
    )

new = '''        if format_name == "famous_movie_commentary":

            # RICH_V1_LEXICAL_REPAIR_BRIDGE_V6_3_5
            #
            # Lexical evidence failure is repairable evidence,
            # not an automatic production-fatal condition.
            #
            # Convert lexical line results into the same narrow
            # failure shape consumed by the existing targeted
            # semantic repair engine. The repair engine itself
            # re-runs BOTH lexical and semantic validators before
            # accepting any replacement.
            evidence_ids = data.get(
                "evidence_ids",
                [],
            )

            evidence_validation = (
                self.claim_evidence_validator.validate(
                    script_lines=lines,
                    evidence_ids=evidence_ids,
                    research=research,
                )
            )

            if not evidence_validation.valid:

                lexical_line_results = []

                for item in evidence_validation.line_results:
                    line_number = int(
                        item.get("line", 0) or 0
                    )

                    line_valid = (
                        item.get("valid") is True
                    )

                    lexical_line_results.append(
                        {
                            "line": line_number,
                            "supported": line_valid,
                            "unsupported_claims": (
                                []
                                if line_valid
                                else [
                                    "Rewrite this line so its "
                                    "factual wording directly "
                                    "matches the cited evidence. "
                                    "Preserve the intended role "
                                    "of the line without adding "
                                    "new facts."
                                ]
                            ),
                            "evidence_ids": item.get(
                                "evidence_ids",
                                [],
                            ),
                            "shared_terms": item.get(
                                "shared_terms",
                                [],
                            ),
                        }
                    )

                class _LexicalRepairValidation:
                    def __init__(
                        self,
                        *,
                        line_results,
                        issues,
                    ):
                        self.valid = False
                        self.line_results = line_results
                        self.issues = list(issues)

                    def to_dict(self):
                        return {
                            "valid": self.valid,
                            "issues": self.issues,
                            "line_results": self.line_results,
                        }

                lexical_repair_validation = (
                    _LexicalRepairValidation(
                        line_results=lexical_line_results,
                        issues=evidence_validation.issues,
                    )
                )

                logger.warning(
                    "Movie lexical evidence validation failed: %s. "
                    "Attempting targeted grounded repair.",
                    evidence_validation.issues,
                )

                repaired_lines = (
                    await self._repair_movie_semantic_failures(
                        script_lines=lines,
                        evidence_ids=evidence_ids,
                        research=research,
                        semantic_validation=(
                            lexical_repair_validation
                        ),
                        topic=topic,
                        movie_title=movie_title,
                    )
                )

                if repaired_lines is None:
                    raise RuntimeError(
                        "Movie script failed lexical evidence "
                        "validation and targeted grounded repair "
                        "failed: "
                        f"{evidence_validation.to_dict()}"
                    )

                lines = repaired_lines

                data["script_lines"] = list(
                    repaired_lines
                )

                # Re-run lexical validation explicitly at the
                # main-pipeline boundary. The repair function
                # already does this internally; this second check
                # keeps the outer contract fail-closed.
                evidence_validation = (
                    self.claim_evidence_validator.validate(
                        script_lines=lines,
                        evidence_ids=evidence_ids,
                        research=research,
                    )
                )

                if not evidence_validation.valid:
                    raise RuntimeError(
                        "Movie lexical evidence repair returned "
                        "content that still failed validation: "
                        f"{evidence_validation.issues}"
                    )

                logger.info(
                    "Targeted lexical movie repair succeeded."
                )

            semantic_validation = (
                await self.semantic_claim_evidence_validator.validate(
                    script_lines=lines,
                    evidence_ids=evidence_ids,
                    research=research,
                )
            )

            if not semantic_validation.valid:

                repaired_lines = (
                    await self._repair_movie_semantic_failures(
                        script_lines=lines,
                        evidence_ids=evidence_ids,
                        research=research,
                        semantic_validation=semantic_validation,
                        topic=topic,
                        movie_title=movie_title,
                    )
                )

                if repaired_lines is None:
                    raise RuntimeError(
                        "Movie script failed semantic evidence "
                        "validation and targeted repair failed: "
                        f"{semantic_validation.to_dict()}"
                    )

                lines = repaired_lines

                data["script_lines"] = list(
                    repaired_lines
                )

                # Fail closed at outer boundary after semantic
                # repair as well.
                final_lexical_validation = (
                    self.claim_evidence_validator.validate(
                        script_lines=lines,
                        evidence_ids=evidence_ids,
                        research=research,
                    )
                )

                if not final_lexical_validation.valid:
                    raise RuntimeError(
                        "Movie semantic repair regressed lexical "
                        "evidence validation: "
                        f"{final_lexical_validation.issues}"
                    )

                final_semantic_validation = (
                    await self.semantic_claim_evidence_validator.validate(
                        script_lines=lines,
                        evidence_ids=evidence_ids,
                        research=research,
                    )
                )

                if not final_semantic_validation.valid:
                    raise RuntimeError(
                        "Movie semantic repair returned content "
                        "that still failed semantic validation: "
                        f"{final_semantic_validation.to_dict()}"
                    )

                logger.info(
                    "Targeted semantic movie repair succeeded."
                )
'''

patched = source.replace(
    old,
    new,
    1,
)

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
# Verify.
# ------------------------------------------------------------

fresh = FILE.read_text(encoding="utf-8")

checks = {
    "marker":
        MARKER in fresh,

    "old_immediate_lexical_kill_removed":
        (
            'raise RuntimeError(\n'
            '                    "Movie script failed claim-evidence validation: "'
        )
        not in fresh,

    "lexical_adapter":
        "lexical_line_results = []"
        in fresh,

    "valid_to_supported_adapter":
        '"supported": line_valid'
        in fresh,

    "targeted_repair":
        fresh.count(
            "await self._repair_movie_semantic_failures("
        ) >= 2,

    "lexical_revalidation":
        "Movie lexical evidence repair returned"
        in fresh,

    "semantic_validation_preserved":
        "await self.semantic_claim_evidence_validator.validate("
        in fresh,

    "semantic_repair_preserved":
        "Movie script failed semantic evidence "
        in fresh,

    "outer_semantic_revalidation":
        "final_semantic_validation"
        in fresh,

    "final_length_gate_preserved":
        "Final generated script failed length "
        in fresh,

    "repair_lexical_gate_preserved":
        "failed lexical validation"
        in fresh,

    "repair_semantic_gate_preserved":
        "next_validation.valid"
        in fresh,
}

print()
print("V6.3.5 VERIFICATION")

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
    print("V6.3.5: FAIL")
    print("Automatic rollback completed.")
    sys.exit(1)

print()
print("V6.3.5: PASS")
print(
    "Lexical evidence failures now enter the existing "
    "targeted grounded repair path."
)
print(
    "Lexical + semantic validators remain mandatory "
    "after repair."
)
print(
    "No evidence threshold was weakened."
)
