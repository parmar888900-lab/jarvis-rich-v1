"""Semantic claim-to-evidence validation for Rich V1 movie commentary."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, asdict

from backend.services.llm_service import LLMService


@dataclass(slots=True)
class SemanticClaimEvidenceResult:
    valid: bool
    issues: list[str]
    line_results: list[dict]

    def to_dict(self) -> dict:
        return asdict(self)


class SemanticClaimEvidenceValidator:
    """
    Use the LLM as a conservative entailment judge.

    The deterministic ClaimEvidenceValidator remains Gate 1.
    This validator is Gate 2 and checks whether the full meaning
    of each narration line is supported by its cited evidence.
    """

    EVIDENCE_PATTERN = re.compile(
        r"\[E(\d+)\]\s*(.*?)(?=\n\s*\[E\d+\]|\Z)",
        flags=re.DOTALL,
    )

    def __init__(
        self,
        llm: LLMService | None = None,
    ) -> None:
        self.llm = (
            llm
            if llm is not None
            else LLMService()
        )

    async def validate(
        self,
        *,
        script_lines: list[str],
        evidence_ids: list[list[str]],
        research: str,
    ) -> SemanticClaimEvidenceResult:

        if len(script_lines) != 4:
            return SemanticClaimEvidenceResult(
                valid=False,
                issues=[
                    "semantic_script_line_count_invalid",
                ],
                line_results=[],
            )

        if len(evidence_ids) != len(script_lines):
            return SemanticClaimEvidenceResult(
                valid=False,
                issues=[
                    "semantic_evidence_line_count_mismatch",
                ],
                line_results=[],
            )

        evidence = self._parse_evidence(
            research
        )

        payload = []

        for index, line in enumerate(
            script_lines,
            start=1,
        ):

            cited_ids = [
                str(item).strip().upper()
                for item in evidence_ids[
                    index - 1
                ]
                if str(item).strip()
            ]

            cited_evidence = {
                evidence_id: evidence.get(
                    evidence_id,
                    "",
                )
                for evidence_id in cited_ids
            }

            payload.append(
                {
                    "line": index,
                    "claim": str(line).strip(),
                    "evidence": cited_evidence,
                }
            )

        messages = [
            {
                "role": "system",
                "content": """
You are a strict factual entailment validator.

Your job is NOT to improve the writing.

For each narration line, decide whether the ENTIRE factual meaning
of the claim is supported by the evidence supplied for that line.

A claim FAILS if it:
- adds a factual detail not present in the evidence
- invents motivation, symbolism, production technique, or intent
- turns a weaker fact into a stronger claim
- attributes an effect, reaction, meaning, or result not supported
- makes unsupported superlative or historical claims
- mixes supported facts with unsupported factual additions

Subjective interpretation may pass ONLY when it is clearly framed as
interpretation and its factual premise is supported.

Return ONLY valid JSON.

Schema:

{
  "valid": true,
  "issues": [],
  "line_results": [
    {
      "line": 1,
      "supported": true,
      "unsupported_claims": []
    }
  ]
}

There must be exactly four line_results.
""",
            },
            {
                "role": "user",
                "content": (
                    "Validate these movie-commentary claims "
                    "against only their cited evidence:\n\n"
                    + json.dumps(
                        payload,
                        indent=2,
                        ensure_ascii=False,
                    )
                ),
            },
        ]

        raw = await self.llm.chat(
            messages,
            json_mode=True,
        )

        data = self._extract_json(
            raw
        )

        if not isinstance(
            data,
            dict,
        ):
            return SemanticClaimEvidenceResult(
                valid=False,
                issues=[
                    "semantic_validator_invalid_response",
                ],
                line_results=[],
            )

        raw_results = data.get(
            "line_results",
            [],
        )

        if (
            not isinstance(raw_results, list)
            or len(raw_results) != 4
        ):
            return SemanticClaimEvidenceResult(
                valid=False,
                issues=[
                    "semantic_validator_line_results_invalid",
                ],
                line_results=[],
            )

        line_results = []
        issues = []

        for index, result in enumerate(
            raw_results,
            start=1,
        ):

            if not isinstance(
                result,
                dict,
            ):
                issues.append(
                    f"line_{index}_semantic_result_invalid"
                )
                continue

            supported = (
                result.get("supported")
                is True
            )

            unsupported = result.get(
                "unsupported_claims",
                [],
            )

            if not isinstance(
                unsupported,
                list,
            ):
                unsupported = [
                    str(unsupported)
                ]

            clean_unsupported = [
                str(item).strip()
                for item in unsupported
                if str(item).strip()
            ]

            if not supported:
                issues.append(
                    f"line_{index}_semantic_evidence_failure"
                )

            line_results.append(
                {
                    "line": index,
                    "supported": supported,
                    "unsupported_claims": (
                        clean_unsupported
                    ),
                }
            )

        return SemanticClaimEvidenceResult(
            valid=(
                not issues
                and len(line_results) == 4
                and all(
                    item["supported"]
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

        output = {}

        for match in cls.EVIDENCE_PATTERN.finditer(
            str(research)
        ):

            evidence_id = (
                f"E{match.group(1)}"
            )

            output[evidence_id] = (
                " ".join(
                    match.group(2).split()
                )
            )

        return output

    @staticmethod
    def _extract_json(
        raw: str,
    ) -> dict:

        if not raw:
            return {}

        cleaned = raw.strip()

        cleaned = re.sub(
            r"```json",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )

        cleaned = cleaned.replace(
            "```",
            "",
        ).strip()

        try:
            value = json.loads(
                cleaned
            )

            return (
                value
                if isinstance(value, dict)
                else {}
            )

        except json.JSONDecodeError:
            pass

        start = cleaned.find("{")
        end = cleaned.rfind("}")

        if (
            start < 0
            or end <= start
        ):
            return {}

        try:
            value = json.loads(
                cleaned[start:end + 1]
            )

            return (
                value
                if isinstance(value, dict)
                else {}
            )

        except json.JSONDecodeError:
            return {}
