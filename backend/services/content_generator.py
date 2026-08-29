import json
import logging
import re

from backend.models.generated_content import GeneratedContent
from backend.services.llm_service import LLMService

logger = logging.getLogger(__name__)


class ContentGenerator:

    MIN_WORDS = 75
    MAX_WORDS = 105

    def __init__(self):
        self.llm = LLMService()

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
                logger.warning(
                    "Content regeneration failed "
                    "(%s words).",
                    self._word_count(
                        retry_data
                    ),
                )

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

        while len(lines) < 4:
            lines.append(
                "Follow for more updates "
                "as this story develops."
            )

        lines = lines[:4]

        return GeneratedContent(
            title=title,
            hashtags=hashtags,
            script_lines=lines,
            metadata={
                "source": topic,
                "generator": "Jarvis Rich V1",
                "word_count": sum(
                    len(line.split())
                    for line in lines
                ),
            },
        )

    ########################################################
    # Content repair
    ########################################################

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
        data: dict,
        research: str,
        banned_terms: list[str],
    ) -> dict | None:

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

        lines = [
            str(line).strip()
            for line in data.get(
                "script_lines",
                []
            )
        ]

        research_text = " ".join(
            str(research).split()
        ).strip()

        if not research_text:
            return None

        # Preserve complete research sentences.
        research_sentences = [
            sentence.strip()
            for sentence in re.split(
                r"(?<=[.!?])\s+",
                research_text,
            )
            if sentence.strip()
        ]

        safe_sentences = []

        for sentence in research_sentences:

            blocked = False

            for term in banned_terms:

                pattern = (
                    r"(?<!\w)"
                    + re.escape(term)
                    + r"(?!\w)"
                )

                if re.search(
                    pattern,
                    sentence,
                    flags=re.IGNORECASE,
                ):
                    blocked = True
                    break

            if not blocked:
                safe_sentences.append(
                    sentence
                )

        if not safe_sentences:
            return None

        candidate_lines = list(
            lines
        )

        total_words = current_words
        line_index = 0

        for sentence in safe_sentences:

            sentence_words = len(
                sentence.split()
            )

            if (
                total_words
                + sentence_words
                > self.MAX_WORDS
            ):
                continue

            base = candidate_lines[
                line_index
            ].rstrip()

            if (
                base
                and base[-1]
                not in ".!?"
            ):
                base += "."

            candidate_lines[
                line_index
            ] = (
                base
                + " "
                + sentence
            ).strip()

            total_words += (
                sentence_words
            )

            line_index = (
                line_index + 1
            ) % 4

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

        system_prompt = """
You are Jarvis, a factual YouTube Shorts script editor.

Return ONLY one valid JSON object.
Do not use markdown or code fences.
Do not include text outside the JSON.

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

    def _build_messages(
        self,
        topic: str,
        research: str,
        previous_words: int = 0,
        retry: bool = False,
    ) -> list[dict]:

        system_prompt = """
You are Jarvis, a YouTube Shorts script writer.

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
4. Line 1 must immediately hook the viewer.
5. Lines 2 and 3 explain the important information.
6. Line 4 concludes and ends with natural engagement.
7. Use only information supported by the research.
8. Do not exaggerate certainty.
9. Do not invent facts.
10. Count the narration words before responding.
"""

        retry_instruction = ""

        if retry:
            retry_instruction = f"""
IMPORTANT RETRY:

Your previous attempt contained approximately
{previous_words} narration words and FAILED validation.

You MUST rewrite the script.

The new script must contain 75-105 total narration words.

Each of the four lines should contain approximately
19-26 words.

Do not shorten the previous script.
Expand it using only the supplied research.
"""

        user_prompt = f"""
TOPIC:

{topic}

RESEARCH:

{research}

{retry_instruction}

Create the final YouTube Shorts script.

Before returning JSON:

- verify there are exactly 4 script_lines
- count the words across those 4 lines
- verify the total is between 75 and 105
- verify every factual claim is supported by the research

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

    ########################################################
    # Validation
    ########################################################

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

        return {
            "title": topic,
            "hashtags": [
                "#shorts",
                "#technology",
                "#trending",
            ],
            "script_lines": [
                (
                    f"{topic} is getting attention, "
                    "and the technology behind it is "
                    "developing quickly as creators "
                    "experiment with increasingly "
                    "automated production tools."
                ),
                (
                    "Current AI video systems are "
                    "improving image quality and motion "
                    "consistency while helping creators "
                    "turn ideas and scripts into visual "
                    "content more efficiently."
                ),
                (
                    "AI tools can also assist with "
                    "narration, captions, editing, and "
                    "other production steps, bringing "
                    "more of the video workflow into "
                    "a connected automated process."
                ),
                (
                    "These improvements show how quickly "
                    "AI-assisted video production is "
                    "changing, although results still "
                    "depend on the tools and material "
                    "being used. What do you think?"
                ),
            ],
        }

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


