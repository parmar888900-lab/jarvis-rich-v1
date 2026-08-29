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

    def _is_valid_content(
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

