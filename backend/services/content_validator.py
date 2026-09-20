"""
Deterministic content-quality validation.

Rejects high-risk or overly absolute claims before
generated content enters the production pipeline.
"""

import re

from backend.models.generated_content import GeneratedContent


class ContentValidator:

    HIGH_RISK_PATTERNS = (
        r"\b100\s*%",
        r"\bguaranteed\b",
        r"\bguarantees\b",
        r"\bproven\b",
        r"\balways\b",
        r"\bnever\b",
        r"\bindistinguishable\b",
        r"\bcompletely\s+identical\b",
        r"\bperfect(?:ed|ly)?\b",
    )

    def validate(
        self,
        content: GeneratedContent,
    ) -> dict:

        script = " ".join(
            content.script_lines
        )

        issues = []

        for pattern in self.HIGH_RISK_PATTERNS:

            matches = re.findall(
                pattern,
                script,
                flags=re.IGNORECASE,
            )

            if matches:

                issues.append(
                    {
                        "type": (
                            "high_risk_claim"
                        ),
                        "pattern": pattern,
                        "matches": matches,
                    }
                )

        return {
            "valid": not issues,
            "issues": issues,
        }

