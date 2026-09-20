"""Claim-to-evidence validation for Rich V1 movie commentary."""

from __future__ import annotations

import re
from dataclasses import dataclass, asdict


@dataclass(slots=True)
class ClaimEvidenceResult:
    valid: bool
    issues: list[str]
    line_results: list[dict]

    def to_dict(self) -> dict:
        return asdict(self)


class ClaimEvidenceValidator:
    """
    Validate that movie-commentary narration lines cite existing
    research evidence and share meaningful factual concepts with it.

    This is a conservative V1 gate. It does not attempt to prove
    philosophical or subjective interpretation.
    """

    MIN_SHARED_TERMS = 2

    STOPWORDS = {
        "about",
        "after",
        "again",
        "against",
        "also",
        "because",
        "been",
        "being",
        "between",
        "both",
        "could",
        "does",
        "from",
        "have",
        "into",
        "more",
        "most",
        "movie",
        "scene",
        "scenes",
        "that",
        "their",
        "there",
        "these",
        "they",
        "this",
        "those",
        "through",
        "very",
        "what",
        "when",
        "where",
        "which",
        "while",
        "with",
        "would",
    }

    EVIDENCE_PATTERN = re.compile(
        r"\[E(\d+)\]\s*(.*?)(?=\n\s*\[E\d+\]|\Z)",
        flags=re.DOTALL,
    )

    def validate(
        self,
        *,
        script_lines: list[str],
        evidence_ids: list[list[str]],
        research: str,
    ) -> ClaimEvidenceResult:

        evidence = self._parse_evidence(
            research
        )

        issues: list[str] = []
        line_results: list[dict] = []

        if len(script_lines) != 4:
            issues.append(
                "script_line_count_invalid"
            )

        if len(evidence_ids) != len(script_lines):
            issues.append(
                "evidence_line_count_mismatch"
            )

        for index, line in enumerate(
            script_lines,
            start=1,
        ):

            cited = (
                evidence_ids[index - 1]
                if index - 1 < len(evidence_ids)
                else []
            )

            if not isinstance(cited, list):
                cited = []

            clean_ids = [
                str(item).strip().upper()
                for item in cited
                if str(item).strip()
            ]

            missing = [
                evidence_id
                for evidence_id in clean_ids
                if evidence_id not in evidence
            ]

            if missing:
                issues.append(
                    f"line_{index}_unknown_evidence"
                )

            supported_text = " ".join(
                evidence[evidence_id]
                for evidence_id in clean_ids
                if evidence_id in evidence
            )

            shared_terms = self._shared_terms(
                line,
                supported_text,
            )

            required_shared_terms = (
                1
                if index == 4
                else self.MIN_SHARED_TERMS
            )

            line_valid = (
                bool(clean_ids)
                and not missing
                and len(shared_terms)
                >= required_shared_terms
            )

            if not clean_ids:
                issues.append(
                    f"line_{index}_has_no_evidence"
                )
            elif (
                not missing
                and len(shared_terms)
                < required_shared_terms
            ):
                issues.append(
                    f"line_{index}_weak_evidence_match"
                )

            line_results.append(
                {
                    "line": index,
                    "valid": line_valid,
                    "evidence_ids": clean_ids,
                    "shared_terms": shared_terms,
                }
            )

        return ClaimEvidenceResult(
            valid=(
                not issues
                and all(
                    item["valid"]
                    for item in line_results
                )
            ),
            issues=issues,
            line_results=line_results,
        )

    @classmethod
    def _parse_evidence(
        cls,
        research: str,
    ) -> dict[str, str]:

        output: dict[str, str] = {}

        for match in cls.EVIDENCE_PATTERN.finditer(
            str(research)
        ):

            evidence_id = (
                f"E{match.group(1)}"
            )

            text = " ".join(
                match.group(2).split()
            )

            output[evidence_id] = text

        return output

    @classmethod
    def _shared_terms(
        cls,
        claim: str,
        evidence: str,
    ) -> list[str]:

        claim_terms = cls._terms(
            claim
        )

        evidence_terms = cls._terms(
            evidence
        )

        return sorted(
            claim_terms.intersection(
                evidence_terms
            )
        )

    @classmethod
    def _terms(
        cls,
        text: str,
    ) -> set[str]:

        words = re.findall(
            r"[a-z0-9]+",
            str(text).lower(),
        )

        return {
            word
            for word in words
            if (
                len(word) >= 4
                and word not in cls.STOPWORDS
            )
        }

