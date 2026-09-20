import json
import logging
import re

from backend.models.generated_content import GeneratedContent
from backend.services.llm_service import LLMService
from backend.services.intelligence.claim_evidence_validator import (
    ClaimEvidenceValidator,
)
from backend.services.intelligence.semantic_claim_evidence_validator import (
    SemanticClaimEvidenceValidator,
)

logger = logging.getLogger(__name__)


class ContentGenerator:

    MIN_WORDS = 75
    MAX_WORDS = 110

    def __init__(self):
        self.llm = LLMService()
        self.claim_evidence_validator = ClaimEvidenceValidator()
        self.semantic_claim_evidence_validator = (
            SemanticClaimEvidenceValidator(
                llm=self.llm
            )
        )


    @staticmethod
    def _is_movie_fact_generation(
        *,
        format_name: str,
        reference_format: str,
    ) -> bool:
        return (
            str(format_name).strip()
            == "famous_movie_commentary"
            or str(reference_format).strip()
            == "movie_facts"
        )

    async def generate(
        self,
        trend: dict,
    ) -> GeneratedContent:

        topic = (
            trend.get("title")
            or trend.get("topic")
            or "Trending Story"
        )

        research = trend.get(
            "research",
            "",
        )

        content_format = trend.get(
            "content_format",
            {},
        )

        if not isinstance(
            content_format,
            dict,
        ):
            content_format = {}

        reference_profile = (
            content_format.get(
                "reference_profile"
            )
            or {}
        )

        reference_format = str(
            reference_profile.get(
                "format_name",
                content_format.get(
                    "format_name",
                    "",
                ),
            )
        ).strip()

        format_name = str(
            content_format.get(
                "format_name",
                "visual_explainer",
            )
        ).strip()

        movie_title = str(
            trend.get(
                "movie_title",
                "",
            )
        ).strip()

        if isinstance(research, list):
            research = "\n".join(
                str(x)
                for x in research
            )

        if not research:
            research = json.dumps(
                trend,
                indent=2,
            )

        ####################################################
        # Attempt 1
        ####################################################

        raw = await self.llm.chat(
            self._build_messages(
                topic=topic,
                research=research,
                format_name=format_name,
                movie_title=movie_title,
                reference_profile=reference_profile,
            ),
            json_mode=True,
        )

        data = self._extract_json(raw)


        ####################################################
        # Attempt 2 - controlled regeneration
        ####################################################

        if not self._is_valid_content(data):

            previous_words = (
                self._word_count(data)
            )

            logger.warning(
                "Initial content invalid "
                "(%s words). Regenerating.",
                previous_words,
            )

            retry_raw = await self.llm.chat(
                self._build_messages(
                    topic=topic,
                    research=research,
                    previous_words=previous_words,
                    retry=True,
                    format_name=format_name,
                    movie_title=movie_title,
                    reference_profile=reference_profile,
            ),
                json_mode=True,
            )

            retry_data = self._extract_json(
                retry_raw
            )


            if self._is_valid_content(
                retry_data
            ):
                data = retry_data

                logger.info(
                    "Content regeneration succeeded."
                )

            else:
                retry_words = self._word_count(
                    retry_data
                )

                logger.warning(
                    "Content regeneration failed "
                    "(%s words). Attempting grounded "
                    "length recovery.",
                    retry_words,
                )

                if self._is_movie_fact_generation(
                    format_name=format_name,
                    reference_format=reference_format,
                ):

                    recovered = (
                        await self._recover_movie_generation_length(
                            data=retry_data,
                            topic=topic,
                            movie_title=movie_title,
                            research=research,
                        )
                    )

                else:

                    recovered = (
                        self._recover_generation_length(
                            data=retry_data,
                            research=research,
                        )
                    )

                if recovered is not None:
                    data = recovered

                    logger.info(
                        "Grounded generation length "
                        "recovery succeeded (%s words).",
                        self._word_count(data),
                    )

                else:
                    data = {}

        ####################################################
        # Emergency fallback
        ####################################################

        if not data:

            logger.warning(
                "Using emergency content fallback."
            )

            data = self._fallback(
                topic=topic,
                research=research,
            )

        ####################################################
        # Normalize
        ####################################################

        title = str(
            data.get(
                "title",
                topic,
            )
        ).strip()

        hashtags = [
            str(tag).strip()
            for tag in data.get(
                "hashtags",
                []
            )
            if str(tag).strip()
        ]

        lines = [
            str(line).strip()
            for line in data.get(
                "script_lines",
                []
            )
            if str(line).strip()
        ]

        if len(lines) != 4:
            raise RuntimeError(
                "Generated content normalization produced "
                f"{len(lines)} script lines; expected exactly 4."
            )

        lines = lines[:4]

        if format_name == "famous_movie_commentary":

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


        ####################################################
        # Final fail-closed script-length guarantee
        ####################################################

        final_word_count = sum(
            len(line.split())
            for line in lines
        )

        if not (
            self.MIN_WORDS
            <= final_word_count
            <= self.MAX_WORDS
        ):
            raise RuntimeError(
                "Final generated script failed length "
                "validation after all generation and "
                "repair stages: "
                f"{final_word_count} words "
                f"(required {self.MIN_WORDS}-"
                f"{self.MAX_WORDS})."
            )

        return GeneratedContent(
            title=title,
            hashtags=hashtags,
            script_lines=lines,
            metadata={
                "source": topic,
                "generator": "Jarvis Rich V1",
                "premise_audit": self.evaluate_premise_strength(topic, reference_format),
                "content_format": format_name,
                "movie_title": movie_title,
                "evidence_ids": (
                    data.get("evidence_ids", [])
                    if format_name == "famous_movie_commentary"
                    else []
                ),
                "word_count": sum(
                    len(line.split())
                    for line in lines
                ),
            },
        )

    ########################################################
    # Content repair
    ########################################################

    async def _recover_movie_generation_length(
        self,
        *,
        data: dict,
        topic: str,
        movie_title: str,
        research: str,
    ) -> dict | None:
        """
        Recover short movie-facts/commentary scripts using a
        bounded evidence-aware LLM retry loop.

        Every accepted candidate must:
        - remain structurally valid
        - contain 75-110 narration words
        - contain exactly four narration lines
        - preserve separate evidence_ids
        - pass claim/evidence validation
        - contain no evidence labels in spoken narration

        Recovery is deliberately bounded to three attempts.
        """

        if not self._is_structurally_valid_content(
            data
        ):
            return None

        current_words = self._word_count(
            data
        )

        if (
            self.MIN_WORDS
            <= current_words
            <= self.MAX_WORDS
        ):
            return data

        if current_words > self.MAX_WORDS:
            return None

        current_candidate = data

        for attempt in range(1, 4):

            candidate_words = self._word_count(
                current_candidate
            )

            current_json = json.dumps(
                current_candidate,
                indent=2,
            )

            missing_words = max(
                0,
                85 - candidate_words,
            )

            if attempt == 1:
                correction = f"""
The current narration has {candidate_words} words.

Rewrite it to 85-100 narration words total.

You need approximately {missing_words} additional
words if the current script is short.

Do not merely repeat existing wording.
Add only useful explanation that is directly
supported by the supplied evidence.
"""
            else:
                correction = f"""
THIS IS RECOVERY ATTEMPT {attempt} OF 3.

The previous recovery still failed validation.

Its narration contains {candidate_words} words.

You MUST return 85-100 narration words.

Use exactly four narration lines.

Aim for 21-25 words per line so the total lands
safely inside the target window.

Before responding:
- count each narration line
- count the total narration words
- verify the total is at least 85
- verify the total is no more than 100
- verify every factual statement is supported
  by the supplied evidence
- verify evidence labels are NOT spoken

Do not shorten the script again.
Do not add filler.
Do not invent facts.
"""

            messages = [
                {
                    "role": "system",
                    "content": f"""
You are repairing a grounded movie-facts
YouTube Short.

Return ONLY one valid JSON object.
Do not return markdown.
Do not return commentary outside JSON.

Keep exactly this structure:

{{
  "title": "string",
  "hashtags": [
    "#tag1",
    "#tag2",
    "#tag3"
  ],
  "script_lines": [
    "line 1",
    "line 2",
    "line 3",
    "line 4"
  ],
  "evidence_ids": [
    ["E1"],
    ["E2"],
    ["E3"],
    ["E4"]
  ]
}}

MANDATORY RULES:

1. Exactly four narration lines.

2. Narration must contain 85-100 words total.

3. Aim for approximately 21-25 words per line.

4. Preserve natural spoken vertical-video narration.

5. Line 1 must preserve the exact curiosity-driving
   premise and create an information gap.

6. Line 2 provides only necessary context.

7. Line 3 contains the strongest concrete supported
   mechanism, example, action, contrast, number,
   or consequence available in the evidence.

8. Line 4 resolves the opening information gap with
   a specific supported payoff.

9. Every line must add new information.

10. Never paste raw research blocks into narration.

11. Never place [E1], [E2], or any evidence label
    inside script_lines.

12. evidence_ids must remain separate from narration.

13. Every factual claim must be supported by the
    supplied grounded evidence.

14. Cite only evidence IDs that actually exist in
    the supplied research.

15. Do not invent filmmaking, production,
    behind-the-scenes, historical, numerical,
    causal, or technical claims.

16. Do not add a generic call to action.

17. Do not add filler merely to reach word count.

18. If additional length is required, add useful
    supported explanation, mechanism, context,
    contrast, or consequence.

19. Count the four narration lines before responding.

20. Count the total narration words before responding.

{correction}
""",
                },
                {
                    "role": "user",
                    "content": f"""
MOVIE:

{movie_title}

TOPIC:

{topic}

CURRENT SCRIPT JSON:

{current_json}

GROUNDED EVIDENCE:

{research}

Produce the corrected 85-100 word script.

Return only the JSON object.
""",
                },
            ]

            raw = await self.llm.chat(
                messages,
                json_mode=True,
            )

            recovered = self._extract_json(
                raw
            )

            if not isinstance(
                recovered,
                dict,
            ):
                logger.warning(
                    "Movie length recovery attempt %s "
                    "returned no valid JSON object.",
                    attempt,
                )
                continue

            if not self._is_structurally_valid_content(
                recovered
            ):
                logger.warning(
                    "Movie length recovery attempt %s "
                    "failed structural validation.",
                    attempt,
                )

                current_candidate = recovered
                continue

            recovered_words = self._word_count(
                recovered
            )

            if not (
                self.MIN_WORDS
                <= recovered_words
                <= self.MAX_WORDS
            ):
                logger.warning(
                    "Movie length recovery attempt %s "
                    "failed length validation: %s words.",
                    attempt,
                    recovered_words,
                )

                current_candidate = recovered
                continue

            recovered_lines = [
                str(line).strip()
                for line in recovered.get(
                    "script_lines",
                    []
                )
            ]

            if any(
                len(line.split()) > 29
                for line in recovered_lines
            ):
                logger.warning(
                    "Movie length recovery attempt %s "
                    "rejected a narration line over "
                    "29 words.",
                    attempt,
                )

                current_candidate = recovered
                continue

            evidence_ids = recovered.get(
                "evidence_ids",
                [],
            )

            validation = (
                self.claim_evidence_validator.validate(
                    script_lines=recovered_lines,
                    evidence_ids=evidence_ids,
                    research=research,
                )
            )

            if not validation.valid:
                logger.warning(
                    "Movie length recovery attempt %s "
                    "failed claim-evidence validation: %s",
                    attempt,
                    validation.issues,
                )

                current_candidate = recovered
                continue

            evidence_label_leak = False

            for line in recovered_lines:

                if re.search(
                    r"\[E\d+\]",
                    line,
                    flags=re.IGNORECASE,
                ):
                    evidence_label_leak = True
                    break

            if evidence_label_leak:
                logger.warning(
                    "Movie length recovery attempt %s "
                    "rejected evidence-label leakage.",
                    attempt,
                )

                current_candidate = recovered
                continue

            logger.info(
                "Movie evidence-aware length recovery "
                "succeeded on attempt %s: %s words.",
                attempt,
                recovered_words,
            )

            return recovered

        logger.warning(
            "Movie evidence-aware length recovery "
            "exhausted 3 bounded attempts."
        )

        return None


    async def _repair_movie_semantic_failures(
        self,
        *,
        script_lines: list[str],
        evidence_ids: list[list[str]],
        research: str,
        semantic_validation,
        topic: str,
        movie_title: str,
    ) -> list[str] | None:
        """
        Repair only semantic evidence failures.

        Up to three controlled repair rounds are allowed.
        Every round is revalidated lexically and semantically.
        """

        evidence_map = {}

        for match in re.finditer(
            r"\[E(\d+)\]\s*(.*?)(?=\n\s*\[E\d+\]|\Z)",
            str(research),
            flags=re.DOTALL,
        ):
            evidence_id = f"E{match.group(1)}"

            evidence_map[evidence_id] = " ".join(
                match.group(2).split()
            )

        working_lines = list(
            script_lines
        )

        current_validation = (
            semantic_validation
        )

        max_attempts = 3

        for attempt in range(
            1,
            max_attempts + 1,
        ):

            failed_lines = [
                item
                for item in current_validation.line_results
                if item.get("supported") is not True
            ]

            if not failed_lines:
                return working_lines

            repair_payload = []

            for failure in failed_lines:

                line_number = int(
                    failure.get(
                        "line",
                        0,
                    )
                    or 0
                )

                if (
                    line_number < 1
                    or line_number > len(working_lines)
                ):
                    return None

                cited_ids = [
                    str(item).strip().upper()
                    for item in evidence_ids[
                        line_number - 1
                    ]
                    if str(item).strip()
                ]

                cited_evidence = {
                    evidence_id: evidence_map.get(
                        evidence_id,
                        "",
                    )
                    for evidence_id in cited_ids
                }

                repair_payload.append(
                    {
                        "line": line_number,
                        "current_text": (
                            working_lines[
                                line_number - 1
                            ]
                        ),
                        "unsupported_claims": (
                            failure.get(
                                "unsupported_claims",
                                [],
                            )
                        ),
                        "evidence_ids": cited_ids,
                        "evidence": cited_evidence,
                    }
                )

            messages = [
                {
                    "role": "system",
                    "content": """
You repair unsupported factual claims in movie commentary.

Return ONLY valid JSON:

{
  "repairs": [
    {
      "line": 3,
      "text": "replacement narration"
    }
  ]
}

STRICT RULES:

1. Rewrite only the requested failed lines.
2. Use only the evidence supplied for that exact line.
3. Remove every unsupported claim identified by the validator.
4. Do not replace one unsupported claim with another unsupported claim.
5. Prefer wording that closely follows the evidence.
6. Do not strengthen the evidence.
7. Do not simplify attribution incorrectly.
8. If multiple studios contributed, do not attribute all work to one studio.
9. If evidence says a filmmaker tried to take another film's effects further, do not change that into "inspired by" unless explicitly supported.
10. Do not invent audience reactions, symbolism, rankings, historical importance, motivations, or production methods.
11. Do not include evidence labels in narration.
12. Keep the narration natural and cinematic.
13. Keep the full script within 75-110 words.
""",
                },
                {
                    "role": "user",
                    "content": (
                        f"REPAIR ATTEMPT: {attempt}\n\n"
                        f"MOVIE:\n{movie_title}\n\n"
                        f"TOPIC:\n{topic}\n\n"
                        "FAILED LINES AND EVIDENCE:\n"
                        + json.dumps(
                            repair_payload,
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

            repair_data = self._extract_json(
                raw
            )

            repairs = repair_data.get(
                "repairs",
                [],
            )

            if not isinstance(
                repairs,
                list,
            ):
                return None

            expected_lines = {
                int(item["line"])
                for item in repair_payload
            }

            repaired_line_numbers = set()

            candidate_lines = list(
                working_lines
            )

            for repair in repairs:

                if not isinstance(
                    repair,
                    dict,
                ):
                    return None

                try:
                    line_number = int(
                        repair.get(
                            "line",
                            0,
                        )
                    )
                except (
                    TypeError,
                    ValueError,
                ):
                    return None

                text = str(
                    repair.get(
                        "text",
                        "",
                    )
                ).strip()

                if (
                    line_number not in expected_lines
                    or not text
                ):
                    return None

                if re.search(
                    r"\[E\d+\]",
                    text,
                    flags=re.IGNORECASE,
                ):
                    return None

                candidate_lines[
                    line_number - 1
                ] = text

                repaired_line_numbers.add(
                    line_number
                )

            if repaired_line_numbers != expected_lines:
                return None

            word_count = sum(
                len(line.split())
                for line in candidate_lines
            )

            if not (
                self.MIN_WORDS
                <= word_count
                <= self.MAX_WORDS
            ):
                logger.warning(
                    "Semantic repair attempt %s "
                    "produced invalid length: %s.",
                    attempt,
                    word_count,
                )
                continue

            lexical_validation = (
                self.claim_evidence_validator.validate(
                    script_lines=candidate_lines,
                    evidence_ids=evidence_ids,
                    research=research,
                )
            )

            if not lexical_validation.valid:
                logger.warning(
                    "Semantic repair attempt %s "
                    "failed lexical validation: %s",
                    attempt,
                    lexical_validation.issues,
                )
                continue

            next_validation = (
                await self.semantic_claim_evidence_validator.validate(
                    script_lines=candidate_lines,
                    evidence_ids=evidence_ids,
                    research=research,
                )
            )

            if next_validation.valid:
                logger.info(
                    "Semantic repair succeeded "
                    "on attempt %s.",
                    attempt,
                )
                return candidate_lines

            logger.warning(
                "Semantic repair attempt %s "
                "still failed: %s",
                attempt,
                next_validation.to_dict(),
            )

            working_lines = candidate_lines
            current_validation = next_validation

        return None


    def _recover_generation_length(
        self,
        data: dict,
        research: str,
    ) -> dict | None:
        """
        Expand a structurally valid but short script using only
        complete sentences already present in supplied research.
        """

        if not self._is_structurally_valid_content(data):
            return None

        current_words = self._word_count(data)

        if self.MIN_WORDS <= current_words <= self.MAX_WORDS:
            return data

        if current_words > self.MAX_WORDS:
            return None

        research_text = " ".join(
            str(research).split()
        ).strip()

        if not research_text:
            return None

        sentences = [
            sentence.strip()
            for sentence in re.split(
                r"(?<=[.!?])\s+",
                research_text,
            )
            if sentence.strip()
        ]

        lines = [
            str(line).strip()
            for line in data.get(
                "script_lines",
                []
            )
        ]

        if len(lines) != 4:
            return None

        existing_text = " ".join(lines).lower()

        safe_sentences = []

        for sentence in sentences:

            if len(sentence.split()) < 5:
                continue

            if sentence.lower() in existing_text:
                continue

            safe_sentences.append(sentence)

        candidate_lines = list(lines)
        total_words = current_words
        line_index = 1

        for sentence in safe_sentences:

            sentence_words = len(
                sentence.split()
            )

            if (
                total_words + sentence_words
                > self.MAX_WORDS
            ):
                continue

            base = candidate_lines[
                line_index
            ].rstrip()

            if (
                base
                and base[-1] not in ".!?"
            ):
                base += "."

            candidate_lines[
                line_index
            ] = (
                base
                + " "
                + sentence
            ).strip()

            total_words += sentence_words

            line_index += 1

            if line_index > 3:
                line_index = 1

            if total_words >= self.MIN_WORDS:
                break

        candidate = {
            **data,
            "script_lines": candidate_lines,
        }

        if not self._is_valid_content(
            candidate
        ):
            return None

        return candidate

    async def repair(
        self,
        content: GeneratedContent,
        trend: dict,
        issues: list[dict],
    ) -> GeneratedContent | None:

        topic = (
            trend.get("title")
            or trend.get("topic")
            or content.title
            or "Trending Story"
        )

        research = trend.get(
            "research",
            "",
        )

        content_format = trend.get(
            "content_format",
            {},
        )

        if not isinstance(
            content_format,
            dict,
        ):
            content_format = {}

        format_name = str(
            content_format.get(
                "format_name",
                "visual_explainer",
            )
        ).strip()

        movie_title = str(
            trend.get(
                "movie_title",
                "",
            )
        ).strip()

        if isinstance(research, list):
            research = "\n".join(
                str(item)
                for item in research
            )

        if not research:
            research = json.dumps(
                trend,
                indent=2,
            )

        original_script = "\n".join(
            content.script_lines
        )

        banned_terms = (
            self._extract_flagged_terms(
                issues
            )
        )

        ####################################################
        # Repair attempt 1
        ####################################################

        raw = await self.llm.chat(
            self._build_repair_messages(
                topic=topic,
                research=research,
                original_script=original_script,
                issues=issues,
                banned_terms=banned_terms,
            ),
            json_mode=True,
        )

        data = self._extract_json(
            raw
        )

        if self._repair_candidate_valid(
            data=data,
            banned_terms=banned_terms,
        ):
            return self._build_repaired_content(
                data=data,
                original=content,
                topic=topic,
                issues=issues,
                attempt=1,
            )

        recovered = self._recover_repair_length(
            data=data,
            research=research,
            banned_terms=banned_terms,
        )

        if recovered is not None:
            logger.info(
                "Repair attempt 1 recovered "
                "deterministically."
            )

            return self._build_repaired_content(
                data=recovered,
                original=content,
                topic=topic,
                issues=issues,
                attempt=1,
            )

        first_words = self._word_count(
            data
        )

        remaining_terms = (
            self._remaining_flagged_terms(
                data=data,
                banned_terms=banned_terms,
            )
        )

        logger.warning(
            "Repair attempt 1 failed. "
            "Words=%s, remaining terms=%s",
            first_words,
            remaining_terms,
        )

        ####################################################
        # Repair attempt 2
        ####################################################

        previous_repair = ""

        if isinstance(data, dict):
            previous_repair = json.dumps(
                data,
                indent=2,
            )

        retry_raw = await self.llm.chat(
            self._build_repair_messages(
                topic=topic,
                research=research,
                original_script=original_script,
                issues=issues,
                banned_terms=banned_terms,
                retry=True,
                previous_repair=previous_repair,
                previous_words=first_words,
                remaining_terms=remaining_terms,
            ),
            json_mode=True,
        )

        retry_data = self._extract_json(
            retry_raw
        )

        if self._repair_candidate_valid(
            data=retry_data,
            banned_terms=banned_terms,
        ):
            logger.info(
                "Repair attempt 2 succeeded."
            )

            return self._build_repaired_content(
                data=retry_data,
                original=content,
                topic=topic,
                issues=issues,
                attempt=2,
            )

        recovered_retry = self._recover_repair_length(
            data=retry_data,
            research=research,
            banned_terms=banned_terms,
        )

        if recovered_retry is not None:
            logger.info(
                "Repair attempt 2 recovered "
                "deterministically."
            )

            return self._build_repaired_content(
                data=recovered_retry,
                original=content,
                topic=topic,
                issues=issues,
                attempt=2,
            )

        logger.warning(
            "Repair attempt 2 failed. "
            "Words=%s, remaining terms=%s",
            self._word_count(
                retry_data
            ),
            self._remaining_flagged_terms(
                data=retry_data,
                banned_terms=banned_terms,
            ),
        )

        return None

    def _build_repaired_content(
        self,
        data: dict,
        original: GeneratedContent,
        topic: str,
        issues: list[dict],
        attempt: int,
    ) -> GeneratedContent:

        lines = [
            str(line).strip()
            for line in data.get(
                "script_lines",
                []
            )
            if str(line).strip()
        ]

        hashtags = [
            str(tag).strip()
            for tag in data.get(
                "hashtags",
                original.hashtags,
            )
            if str(tag).strip()
        ]

        return GeneratedContent(
            title=str(
                data.get(
                    "title",
                    original.title,
                )
            ).strip(),
            hashtags=hashtags,
            script_lines=lines,
            metadata={
                **original.metadata,
                "source": topic,
                "generator": "Jarvis Rich V1",
                "repaired": True,
                "repair_attempt": attempt,
                "repair_issues": issues,
                "word_count": sum(
                    len(line.split())
                    for line in lines
                ),
            },
        )

    def _recover_repair_length(
        self,
        *,
        data: dict,
        research: str,
        banned_terms: list[str],
    ) -> dict | None:
        """
        Deterministically recover an undersized repair
        using only grounded research.

        Fail closed if structure, length, line limits,
        or banned-term validation cannot be satisfied.
        """

        if not self._is_structurally_valid_content(data):
            return None

        current_words = self._word_count(data)

        remaining_terms = self._remaining_flagged_terms(
            data=data,
            banned_terms=banned_terms,
        )

        if (
            self.MIN_WORDS
            <= current_words
            <= self.MAX_WORDS
            and not remaining_terms
        ):
            return data

        if current_words > self.MAX_WORDS:
            return None

        candidate = dict(data)

        candidate["script_lines"] = [
            str(line).strip()
            for line in data.get(
                "script_lines",
                [],
            )
        ]

        if len(candidate["script_lines"]) != 4:
            return None

        import re

        raw_sentences = re.split(
            r"(?<=[.!?])\s+",
            str(research or "").strip(),
        )

        additions = []

        existing_text = " ".join(
            candidate["script_lines"]
        ).lower()

        for raw_sentence in raw_sentences:

            sentence = " ".join(
                str(raw_sentence).split()
            ).strip()

            words = sentence.split()

            if len(words) < 5:
                continue

            if len(words) > 18:
                continue

            lowered = sentence.lower()

            if lowered in existing_text:
                continue

            flagged = False

            for term in banned_terms:

                clean_term = str(term).strip().lower()

                if clean_term and clean_term in lowered:
                    flagged = True
                    break

            if flagged:
                continue

            additions.append(sentence)

        target_lines = [1, 2, 3]

        for addition in additions:

            if self._word_count(candidate) >= 85:
                break

            placed = False

            for line_index in target_lines:

                current_line = candidate[
                    "script_lines"
                ][line_index]

                combined = (
                    current_line.rstrip(" .")
                    + ". "
                    + addition
                ).strip()

                if len(combined.split()) > 29:
                    continue

                trial = dict(candidate)

                trial["script_lines"] = list(
                    candidate["script_lines"]
                )

                trial["script_lines"][
                    line_index
                ] = combined

                trial_words = self._word_count(
                    trial
                )

                if trial_words > self.MAX_WORDS:
                    continue

                candidate = trial
                placed = True
                break

            if not placed:
                continue

        if not self._is_valid_content(candidate):
            return None

        final_words = self._word_count(candidate)

        if not (
            self.MIN_WORDS
            <= final_words
            <= self.MAX_WORDS
        ):
            return None

        if any(
            len(str(line).split()) > 29
            for line in candidate["script_lines"]
        ):
            return None

        if self._remaining_flagged_terms(
            data=candidate,
            banned_terms=banned_terms,
        ):
            return None

        return candidate

    def _repair_candidate_valid(
        self,
        data: dict,
        banned_terms: list[str],
    ) -> bool:

        if not self._is_valid_content(
            data
        ):
            return False

        remaining = (
            self._remaining_flagged_terms(
                data=data,
                banned_terms=banned_terms,
            )
        )

        if remaining:
            logger.warning(
                "Repair still contains "
                "flagged terms: %s",
                remaining,
            )
            return False

        return True

    @staticmethod
    def _extract_flagged_terms(
        issues: list[dict],
    ) -> list[str]:

        terms = []

        for issue in issues:

            matches = issue.get(
                "matches",
                [],
            )

            if not isinstance(
                matches,
                list,
            ):
                continue

            for match in matches:

                term = str(
                    match
                ).strip()

                if (
                    term
                    and term.lower()
                    not in {
                        existing.lower()
                        for existing in terms
                    }
                ):
                    terms.append(
                        term
                    )

        return terms

    @staticmethod
    def _remaining_flagged_terms(
        data: dict,
        banned_terms: list[str],
    ) -> list[str]:

        if not isinstance(
            data,
            dict,
        ):
            return list(
                banned_terms
            )

        lines = data.get(
            "script_lines",
            [],
        )

        if not isinstance(
            lines,
            list,
        ):
            return list(
                banned_terms
            )

        script = " ".join(
            str(line)
            for line in lines
        )

        remaining = []

        for term in banned_terms:

            pattern = (
                r"(?<!\w)"
                + re.escape(term)
                + r"(?!\w)"
            )

            if re.search(
                pattern,
                script,
                flags=re.IGNORECASE,
            ):
                remaining.append(
                    term
                )

        return remaining

    def _build_repair_messages(
        self,
        topic: str,
        research: str,
        original_script: str,
        issues: list[dict],
        banned_terms: list[str],
        retry: bool = False,
        previous_repair: str = "",
        previous_words: int = 0,
        remaining_terms: list[str] | None = None,
    ) -> list[dict]:

        issue_text = json.dumps(
            issues,
            indent=2,
        )

        banned_text = (
            ", ".join(
                banned_terms
            )
            or "None"
        )

        retry_text = ""

        if retry:

            remaining_text = (
                ", ".join(
                    remaining_terms or []
                )
                or "None"
            )

            retry_text = f"""
THIS IS REPAIR ATTEMPT 2.

The first repair failed.

Previous word count:
{previous_words}

Required word count:
75-105.

Flagged terms still present:
{remaining_text}

Previous failed repair:

{previous_repair}

Rewrite it again rather than copying it.

If it was below 75 words, expand only with
information supported by the research.

None of the banned terms may appear.
"""

        system_prompt = f"""
You are Jarvis, a factual YouTube Shorts script editor.

Return ONLY one valid JSON object.
Do not use markdown or code fences.
Do not include text outside the JSON.

Use exactly this schema:

{{
  "title": "string",
  "hashtags": [
    "#hashtag1",
    "#hashtag2",
    "#hashtag3"
  ],
  "script_lines": [
    "line 1",
    "line 2",
    "line 3",
    "line 4"
  ]
}}

MANDATORY RULES:

1. Exactly four narration lines.
2. EACH line must contain about 19-26 words.
3. Total narration must contain 75-105 words.
4. Use only claims supported by the research.
5. Remove every flagged high-risk claim.
6. Do not invent replacement facts.
7. Do not make absolute predictions.
8. Banned terms must not appear anywhere
   inside script_lines.
9. Count the words before responding.
"""

        user_prompt = f"""
TOPIC:

{topic}

RESEARCH:

{research}

ORIGINAL SCRIPT:

{original_script}

VALIDATION ISSUES:

{issue_text}

BANNED TERMS:

{banned_text}

The banned terms must not appear anywhere
inside script_lines.

Do not use a banned word even to negate it.
For example, if "indistinguishable" is banned,
do not write "not indistinguishable".

{retry_text}

Before returning:

- verify exactly 4 script_lines
- verify 75-105 total narration words
- verify each line is approximately 19-26 words
- verify no banned term appears
- verify every factual claim is supported
  by the research

Return only JSON.
"""

        return [
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": user_prompt,
            },
        ]

    ########################################################
    # Prompt construction
    ########################################################

    @staticmethod
    def _reference_script_instruction(
        reference_profile: dict | None,
    ) -> str:
        profile = (
            reference_profile
            if isinstance(
                reference_profile,
                dict,
            )
            else {}
        )

        name = str(
            profile.get(
                "format_name",
                "",
            )
        ).strip()

        objective = str(
            profile.get(
                "story_objective",
                profile.get(
                    "viewer_objective",
                    "",
                ),
            )
        ).strip()

        hook = str(
            profile.get(
                "hook_strategy",
                "",
            )
        ).strip()

        progression = str(
            profile.get(
                "progression",
                "",
            )
        ).strip()

        payoff = str(
            profile.get(
                "payoff_strategy",
                "",
            )
        ).strip()

        details = [
            (
                f"REFERENCE FORMAT: {name}"
                if name
                else ""
            ),
            (
                f"VIEWER OBJECTIVE: {objective}"
                if objective
                else ""
            ),
            (
                f"HOOK STRATEGY: {hook}"
                if hook
                else ""
            ),
            (
                f"PROGRESSION: {progression}"
                if progression
                else ""
            ),
            (
                f"PAYOFF: {payoff}"
                if payoff
                else ""
            ),
            (
                "The four narration lines are four "
                "STORY STAGES, not four visual shots. "
                "Downstream editing may split each stage "
                "into multiple visual micro-beats."
            ),
            (
                "Open with the strongest concrete fact, "
                "contrast, consequence, recognizable entity, "
                "number, or information gap available in the "
                "research. Do not begin like a school report."
            ),
            (
                "Maintain forward pressure: hook, context, "
                "specific evidence or mechanism, escalation, "
                "then a satisfying payoff."
            ),
            (
                "Avoid filler, generic introductions, "
                "repetition, vague adjectives, engagement "
                "bait, and unsupported claims."
            ),
        ]

        return "\n".join(
            item
            for item in details
            if item
        )


    @staticmethod
    def evaluate_premise_strength(
        topic: str,
        reference_format: str = "",
    ) -> dict:
        clean = " ".join(
            str(topic).split()
        ).strip()

        lower = clean.lower()

        score = 50
        reasons: list[str] = []

        if not clean:
            return {
                "score": 0,
                "strong": False,
                "reasons": ["empty_topic"],
                "reference_format": reference_format,
                "advisory_only": True,
            }

        generic_patterns = (
            "how filmmakers use",
            "the importance of",
            "ways to",
            "how technology is changing",
            "camera movement to",
            "introduction to",
            "history of",
            "basics of",
            "role of",
            "benefits of",
            "types of",
            "what is filmmaking",
            "how movies are made",
        )

        if any(
            phrase in lower
            for phrase in generic_patterns
        ):
            score -= 24
            reasons.append(
                "generic_instructional_wording"
            )

        broad_subjects = {
            "filmmaking",
            "cinema",
            "technology",
            "science",
            "engineering",
            "business",
            "movies",
            "editing",
        }

        words = [
            token.strip(
                ".,:;!?()[]{}\"'"
            ).lower()
            for token in clean.split()
        ]

        meaningful = [
            word
            for word in words
            if len(word) >= 4
        ]

        if (
            len(meaningful) <= 3
            and any(
                word in broad_subjects
                for word in meaningful
            )
        ):
            score -= 20
            reasons.append(
                "premise_too_broad"
            )

        curiosity_markers = (
            "why ",
            "how ",
            "secret",
            "hidden",
            "inside",
            "actually",
            "never",
            "only",
            "million",
            "billion",
            "most expensive",
            "largest",
            "fastest",
            "smallest",
            "deepest",
            "highest",
            "rare",
            "impossible",
            "unexpected",
            "without",
            "instead of",
        )

        if any(
            marker in lower
            for marker in curiosity_markers
        ):
            score += 10
            reasons.append(
                "curiosity_gap"
            )

        mechanism_markers = (
            "because",
            "works",
            "uses",
            "made",
            "built",
            "creates",
            "causes",
            "prevents",
            "survives",
            "costs",
            "worth",
            "failed",
            "changed",
            "became",
            "happens",
            "recorded",
            "designed",
        )

        if any(
            marker in lower
            for marker in mechanism_markers
        ):
            score += 8
            reasons.append(
                "mechanism_or_consequence"
            )

        specificity_markers = (
            "$",
            "%",
            "km",
            "mph",
            "kg",
            "million",
            "billion",
            "seconds",
            "minutes",
            "years",
            "degrees",
        )

        has_number = any(
            char.isdigit()
            for char in clean
        )

        if has_number:
            score += 10
            reasons.append(
                "numeric_specificity"
            )

        if any(
            marker in lower
            for marker in specificity_markers
        ):
            score += 5
            reasons.append(
                "measurable_detail"
            )

        # Titles with enough concrete language generally provide
        # better visual and narrative handles than broad labels.
        if 5 <= len(meaningful) <= 14:
            score += 8
            reasons.append(
                "specific_premise_length"
            )

        # Question-shaped premises receive only a small bonus.
        # "Why" or "how" alone must not make a weak topic strong.
        if lower.startswith(
            ("why ", "how ", "what ")
        ):
            score += 4
            reasons.append(
                "question_structure"
            )

        score = max(
            0,
            min(
                100,
                score,
            ),
        )

        return {
            "score": score,
            "strong": score >= 65,
            "reasons": reasons,
            "reference_format": reference_format,
            "advisory_only": True,
        }

    def _build_messages(
        self,
        topic: str,
        research: str,
        previous_words: int = 0,
        retry: bool = False,
        format_name: str = "visual_explainer",
        movie_title: str = "",
        reference_profile: dict | None = None,
    ) -> list[dict]:

        reference_instruction = (
            self._reference_script_instruction(
                reference_profile
            )
        )


        if format_name == "famous_movie_commentary":

            system_prompt = """
You are Jarvis, writing an original high-retention YouTube Short commentary about a famous movie.

Return ONLY one valid JSON object.
Never use markdown or code fences.
Never add text outside the JSON.

Use exactly this schema:

{
  "title": "string",
  "hashtags": [
    "#hashtag1",
    "#hashtag2",
    "#hashtag3"
  ],
  "script_lines": [
    "line 1",
    "line 2",
    "line 3",
    "line 4"
  ],
  "evidence_ids": [
    ["E1"],
    ["E2"],
    ["E3"],
    ["E4"]
  ]
}

MOVIE COMMENTARY RULES:

EVIDENCE RULES:

- Research facts are labelled [E1], [E2], [E3], and so on.
- evidence_ids must contain exactly four lists, one for each script line.
- Every script line must cite at least one real evidence ID.
- Cite only IDs that actually exist in the supplied research.
- The factual meaning of each line must be supported by its cited evidence.
- A line may cite multiple evidence IDs when needed.
- Do not cite evidence merely because it mentions the same movie.
- Interpretation is allowed only when its factual premise is supported by cited evidence.


1. Write exactly four narration lines.
2. Total narration must be 75-105 words.
3. Line 1 must immediately hook the viewer with the specific movie angle.
4. Never begin with generic phrases such as "Did you know" or "You won't believe".
5. Line 2 gives only the context needed to understand the point.
6. Line 3 explains the strongest concrete filmmaking, VFX, editing, character, production, or storytelling detail supported by the research.
7. Line 4 gives the payoff: explain why the scene, technique, or decision is effective or important.
8. Write like fast cinematic commentary, not a school report.
9. Add original explanation instead of merely retelling the scene.
10. Every line must introduce a new concrete detail, mechanism, or consequence.
11. No narration line may exceed 29 words.
12. Do not open by defining filmmaking, cinema, editing, visual effects, sound design, acting, or another broad category.
13. Keep the specific movie angle active in every narration line.
14. Preserve an information gap through the middle of the Short.
15. Put the strongest supported filmmaking, production, character, editing, VFX, sound, or storytelling detail in line 3.
16. Make line 4 resolve the opening angle instead of ending with a generic summary.
17. Do not include generic calls to action.
11. Every factual claim must be supported by the supplied research.
12. Do not invent behind-the-scenes details.
13. Never claim a specific visual-effects technique was used unless the research explicitly supports it.
14. If the evidence only supports a broader conclusion, state only that broader conclusion.
15. Do not confuse information about the comic-book character with information about the film.
16. Do not compare the movie to another movie unless the supplied research explicitly makes that comparison.
17. Avoid unsupported adjectives such as revolutionary, groundbreaking, extreme, iconic, or unprecedented.
18. Prefer a concrete researched detail over promotional-sounding language.
19. Aim for 85-100 words so the result remains safely above the minimum.
20. Do not claim that a scene makes viewers feel awe, fear, terror, excitement, immersion, tension, or any other audience reaction unless the cited research explicitly supports that reaction.
21. Prefer concrete statements about the filmmaking, visual effects, action design, dimensions, production choices, or documented critical response.
22. Do not turn your own interpretation into a factual statement.
23. Aim for 85-100 narration words.
24. Count the narration words before returning JSON.
"""

        else:

            system_prompt = """
You are Jarvis, a YouTube Shorts script writer.\n\nREFERENCE STORY GRAMMAR:\n{reference_instruction}

Return ONLY one valid JSON object.
Never use markdown or code fences.
Never add text outside the JSON.

Use exactly this schema:

{
  "title": "string",
  "hashtags": [
    "#hashtag1",
    "#hashtag2",
    "#hashtag3"
  ],
  "script_lines": [
    "line 1",
    "line 2",
    "line 3",
    "line 4"
  ]
}

SCRIPT RULES:

1. Exactly four narration lines.
2. Total narration MUST be 75-105 words.
3. Aim for 19-26 words per narration line.
4. No narration line may exceed 29 words.
5. Line 1 must immediately open on the exact curiosity-driving premise, recognizable subject, surprising fact, unusual mechanism, dramatic consequence, or price/value question.
6. Never begin by defining the broad subject or category.
7. Never begin with generic bait such as "Did you know" or "You won't believe".
8. Line 1 must create a clear information gap.
9. Line 2 gives only the context required to deepen that information gap.
10. Line 3 delivers the strongest concrete supported detail, mechanism, example, number, action, contrast, or consequence.
11. Line 4 resolves the opening information gap with a specific payoff.
12. Every narration line must add genuinely new information.
13. Keep the exact topic active throughout the script.
14. Prefer concrete nouns, actions, mechanisms, numbers, names, objects, locations, and visible cause-and-effect.
15. Remove broad history, definitions, and encyclopedia background unless essential to the exact premise.
16. Avoid school-report narration.
17. Avoid vague filler when concrete supported information is available.
18. Use compact spoken sentences designed for fast vertical video.
19. Maintain forward pressure from one line to the next.
20. Use only information supported by the research.
21. Never invent specificity for drama.
22. Do not exaggerate certainty.
23. Do not invent facts.
24. Do not add generic calls to action.
25. Count the narration words before responding.
26. Verify every line is 29 words or fewer before responding.
"""

        retry_instruction = ""

        if retry:

            retry_instruction = f"""
IMPORTANT RETRY:

Your previous attempt contained approximately
{previous_words} narration words and FAILED validation.

Rewrite the entire script.

The new script must contain 75-105 total narration words.

Keep exactly four script_lines.

Do not shorten the previous script.

Expand only with information supported by the supplied research.

For movie commentary, remove unsupported comparison or promotional language.

Do NOT use:
- groundbreaking
- cutting-edge
- Inception comparisons
- practical effects
- Eastern mysticism

unless those exact ideas are explicitly supported by the research.
"""

        user_prompt = f"""
TOPIC:

{topic}

CONTENT FORMAT:

{format_name}

MOVIE:

{movie_title if movie_title else "N/A"}

RESEARCH:

{research}

{retry_instruction}

Create the final YouTube Shorts script.

Before returning JSON:

- verify there are exactly 4 script_lines
- count the words across those 4 lines
- verify the total is between 75 and 105
- verify no script line exceeds 29 words
- verify line 1 begins with the exact premise rather than a broad definition
- verify every line adds new information
- verify line 3 contains the strongest concrete supported detail
- verify line 4 resolves the opening information gap
- verify every factual claim is supported by the research
- remove unsupported production or behind-the-scenes claims
- remove encyclopedia-style background that does not advance the exact premise
- remove repeated ideas
- remove vague filler

Return only the JSON object.
"""

        return [
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": user_prompt,
            },
        ]

    # Validation
    ########################################################

    def _movie_script_has_unsupported_language(
        self,
        data: dict,
        research: str,
    ) -> bool:
        """
        Reject movie-commentary embellishments unless
        the supplied research contains supporting evidence.
        """

        if not isinstance(data, dict):
            return False

        lines = data.get(
            "script_lines",
            [],
        )

        if not isinstance(lines, list):
            return False

        script = " ".join(
            str(line)
            for line in lines
        ).lower()

        evidence = str(
            research
        ).lower()

        guarded_terms = {
            "inception": (
                "inception",
            ),
            "practical effects": (
                "practical effect",
                "practical effects",
            ),
            "eastern mysticism": (
                "eastern mysticism",
            ),
            "groundbreaking": (
                "groundbreaking",
            ),
            "cutting-edge": (
                "cutting-edge",
                "cutting edge",
            ),
        }

        for phrase, evidence_terms in guarded_terms.items():

            if phrase not in script:
                continue

            if not any(
                term in evidence
                for term in evidence_terms
            ):
                logger.warning(
                    "Movie script rejected unsupported "
                    "language: %s",
                    phrase,
                )
                return True

        return False


    def _is_structurally_valid_content(
        self,
        data: dict,
    ) -> bool:

        if not isinstance(data, dict):
            return False

        title = data.get("title")
        hashtags = data.get("hashtags")
        lines = data.get("script_lines")

        if (
            not isinstance(title, str)
            or not title.strip()
        ):
            return False

        if (
            not isinstance(hashtags, list)
            or len(hashtags) < 3
        ):
            return False

        if not all(
            isinstance(tag, str)
            and tag.strip()
            for tag in hashtags
        ):
            return False

        if (
            not isinstance(lines, list)
            or len(lines) != 4
        ):
            return False

        if not all(
            isinstance(line, str)
            and line.strip()
            for line in lines
        ):
            return False

        return True

    def _is_valid_content(
        self,
        data: dict,
    ) -> bool:

        if not self._is_structurally_valid_content(
            data
        ):
            return False

        word_count = self._word_count(
            data
        )

        if not (
            self.MIN_WORDS
            <= word_count
            <= self.MAX_WORDS
        ):

            logger.warning(
                "Script length validation failed: "
                "%s words.",
                word_count,
            )

            return False

        return True

    ########################################################
    # Word counting
    ########################################################

    @staticmethod
    def _word_count(
        data: dict,
    ) -> int:

        if not isinstance(data, dict):
            return 0

        lines = data.get(
            "script_lines",
            [],
        )

        if not isinstance(lines, list):
            return 0

        return sum(
            len(str(line).split())
            for line in lines
        )

    ########################################################
    # Emergency fallback
    ########################################################

    def _fallback(
        self,
        topic: str,
        research: str,
    ) -> dict:
        """
        Rich V1 does not fabricate generic fallback content.

        If grounded content generation fails, the production cycle must
        stop rather than publishing an unrelated or generic script.
        """

        logger.error(
            "Content generation fallback blocked for topic: %s",
            topic,
        )

        raise RuntimeError(
            f"Grounded content generation failed for topic: {topic}"
        )

    ########################################################
    # JSON extraction
    ########################################################

    def _extract_json(
        self,
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

            parsed = json.loads(
                cleaned
            )

            if isinstance(parsed, dict):
                return parsed

        except json.JSONDecodeError:
            pass

        start = cleaned.find("{")
        end = cleaned.rfind("}")

        if (
            start == -1
            or end == -1
            or end <= start
        ):
            return {}

        candidate = cleaned[
            start:end + 1
        ]

        try:

            parsed = json.loads(
                candidate
            )

            if isinstance(parsed, dict):
                return parsed

        except json.JSONDecodeError as exc:

            logger.warning(
                "Failed to parse LLM JSON: %s",
                exc,
            )

        return {}






















