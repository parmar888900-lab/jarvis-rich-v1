"""Angle-aware research for famous-movie commentary."""

from __future__ import annotations

import re

from backend.services.research.knowledge_pack import (
    KnowledgePack,
)
from backend.services.research.providers.wikipedia import (
    WikipediaProvider,
)


class MovieResearchService:
    """
    Research the actual film and extract material relevant to the
    commentary angle.

    This service does not authorize footage.
    """

    MOVIE_PAGE_ALIASES = {
        "Doctor Strange": "Doctor Strange (2016 film)",
        "Avengers Endgame": "Avengers: Endgame",
        "Interstellar": "Interstellar (film)",
        "The Dark Knight": "The Dark Knight (film)",
        "Spider-Man No Way Home": (
            "Spider-Man: No Way Home"
        ),
        "Inception": "Inception",
        "Iron Man": "Iron Man (2008 film)",
        "Jurassic Park": "Jurassic Park (film)",
        "The Matrix": "The Matrix",
        "Pirates of the Caribbean": (
            "Pirates of the Caribbean: "
            "The Curse of the Black Pearl"
        ),
    }

    ANGLE_ALIASES = {
        "suit-building": {
            "mark i", "armor", "armour", "winston", "cave",
            "yinsen", "hammer", "welding", "suit",
        },
        "mirror dimension": {
            "mirror",
            "dimension",
            "visual effects",
            "effects",
            "city",
            "distortion",
            "cgi",
            "computer-generated",
            "geometry",
        },
        "final battle": {
            "battle",
            "climax",
            "final",
            "production",
            "visual effects",
            "effects",
        },
        "docking scene": {
            "docking",
            "spacecraft",
            "editing",
            "music",
            "production",
        },
        "bullet-time": {
            "bullet",
            "time",
            "visual effects",
            "camera",
            "photography",
        },
    }

    ANGLE_EXCLUSIONS = {
        "suit-building": {
            "iron monger",
            "war machine",
            "mark iii",
            "mark iv",
            "final battle",
        },
    }

    STOPWORDS = {
        "why",
        "how",
        "the",
        "this",
        "that",
        "these",
        "those",
        "scene",
        "scenes",
        "work",
        "works",
        "well",
        "movie",
        "film",
        "was",
        "were",
        "are",
        "and",
        "from",
        "with",
        "into",
        "first",
        "became",
        "iconic",
    }

    def __init__(self) -> None:
        self.wikipedia = WikipediaProvider()

    def research(
        self,
        *,
        movie_title: str,
        commentary_topic: str,
    ) -> KnowledgePack:

        pack = KnowledgePack(
            topic=commentary_topic
        )

        page_title = (
            self.MOVIE_PAGE_ALIASES.get(
                movie_title,
                movie_title,
            )
        )

        page = self.wikipedia.wiki.page(
            page_title
        )

        if not page.exists():
            print(
                "[MovieResearch] Movie page not found: "
                f"{page_title}"
            )
            return pack

        source = {
            "title": page.title,
            "content": page.summary[:3000],
            "source": "Wikipedia",
            "url": page.fullurl,
            "confidence": 0.95,
        }

        pack.add_source(source)

        full_text = str(
            page.text or ""
        ).strip()

        angle_terms = self._angle_terms(
            commentary_topic
        )
        # Film names occur throughout the page and otherwise promote box
        # office/release facts above evidence about the requested sequence.
        angle_terms.difference_update(re.findall(r"[a-z0-9]+", movie_title.lower()))

        relevant = self._extract_relevant_sentences(
            full_text,
            angle_terms,
            minimum_matches=(2 if self._matched_angle(commentary_topic) else 1),
            excluded_phrases=self._angle_exclusions(commentary_topic),
        )

        ####################################################
        # The summary remains source context, but it must not become a giant
        # evidence item. Earlier versions labelled the whole summary E1, which
        # let an on-topic phrase elsewhere in E1 legitimize unrelated casting,
        # release, and box-office claims.
        ####################################################

        summary = str(
            page.summary or ""
        ).strip()

        for sentence in relevant[:10]:
            pack.add_fact(
                sentence
            )

        combined_parts = []

        if summary:
            combined_parts.append(
                summary[:2200]
            )

        combined_parts.extend(
            relevant[:10]
        )

        if combined_parts:
            pack.set_summary(
                "\n\n".join(
                    combined_parts
                )[:7000]
            )

        pack.category = (
            "Famous Movie Commentary"
        )

        ####################################################
        # Higher confidence requires angle-specific evidence.
        ####################################################

        if relevant:
            pack.score = 90.0
        elif summary:
            pack.score = 55.0
        else:
            pack.score = 0.0

        return pack

    def _angle_terms(
        self,
        topic: str,
    ) -> set[str]:

        lower = topic.lower()

        terms: set[str] = set()

        for trigger, aliases in (
            self.ANGLE_ALIASES.items()
        ):
            if trigger in lower:
                terms.update(
                    aliases
                )

        words = re.findall(
            r"[a-z0-9\-]+",
            lower,
        )

        for word in words:

            if (
                len(word) < 4
                or word in self.STOPWORDS
            ):
                continue

            terms.add(word)

        return terms

    @classmethod
    def _matched_angle(cls, topic: str) -> str:
        lower = str(topic).lower()
        return next((trigger for trigger in cls.ANGLE_ALIASES if trigger in lower), "")

    @classmethod
    def _angle_exclusions(cls, topic: str) -> set[str]:
        return cls.ANGLE_EXCLUSIONS.get(cls._matched_angle(topic), set())

    @staticmethod
    def _extract_relevant_sentences(
        text: str,
        terms: set[str],
        minimum_matches: int = 1,
        excluded_phrases: set[str] | None = None,
    ) -> list[str]:

        if not text.strip():
            return []

        sentences = [
            sentence.strip()
            for sentence in re.split(
                r"(?<=[.!?])\s+",
                " ".join(
                    text.split()
                ),
            )
            if sentence.strip()
        ]

        scored = []

        for sentence in sentences:

            lower = sentence.lower()

            if any(phrase in lower for phrase in (excluded_phrases or set())):
                continue

            matches = sum(
                1
                for term in terms
                if term in lower
            )

            if matches < max(1, int(minimum_matches)):
                continue

            scored.append(
                (
                    matches,
                    len(sentence),
                    sentence,
                )
            )

        scored.sort(
            key=lambda item: (
                item[0],
                item[1],
            ),
            reverse=True,
        )

        output = []
        seen = set()

        for _, _, sentence in scored:

            key = sentence.lower()

            if key in seen:
                continue

            seen.add(key)
            output.append(sentence)

        return output

    @staticmethod
    def build_research_text(
        pack: KnowledgePack,
    ) -> str:
        """
        Build an explicit evidence pack for movie commentary.

        Each research fact receives a stable evidence ID so the
        script generator can cite exactly which facts support
        each narration line.
        """

        evidence = []

        for index, fact in enumerate(
            pack.facts,
            start=1,
        ):

            clean = str(
                fact
            ).strip()

            if not clean:
                continue

            evidence.append(
                f"[E{index}] {clean}"
            )

        return "\n\n".join(
            evidence
        )
