"""Evergreen research service for Jarvis Rich V1."""

from __future__ import annotations

import re

from backend.services.research.confidence import (
    ResearchConfidenceScorer,
)
from backend.services.research.knowledge_pack import (
    KnowledgePack,
)
from backend.services.research.providers.wikipedia import (
    WikipediaProvider,
)
from backend.services.research.research_memory import (
    ResearchMemory,
)
from backend.services.research.research_service import (
    sanitize_topic,
)


class EvergreenResearchService:
    """
    Background research for evergreen short-form content.

    Current-news providers are intentionally excluded.
    """

    RESEARCH_ALIASES = {
        "train wheel": [
            "Railway wheel",
            "Wheelset",
            "Railway wheel flange",
        ],
        "airplane window": [
            "Aircraft cabin",
            "Aircraft fuselage",
            "De Havilland Comet",
        ],
        "suspension bridge": [
            "Suspension bridge",
            "Bridge",
        ],
        "skyscraper": [
            "Skyscraper",
            "Structural engineering",
        ],
        "black box": [
            "Flight recorder",
            "Flight data recorder",
        ],
        "rocket": [
            "Rocket",
            "Rocket engine",
        ],
        "satellite": [
            "Satellite",
            "Orbit",
        ],
        "gps": [
            "Global Positioning System",
        ],
        "mechanical watch": [
            "Mechanical watch",
            "Watch",
        ],
        "private jet": [
            "Business jet",
        ],
        "supercar": [
            "Supercar",
            "Sports car",
        ],
        "data center": [
            "Data center",
        ],
        "noise cancelling": [
            "Active noise control",
            "Noise-cancelling headphones",
        ],
        "green screen": [
            "Chroma key",
        ],
        "shipping container": [
            "Intermodal container",
            "Containerization",
        ],
        "barcode": [
            "Barcode",
        ],
        "elevator": [
            "Elevator",
        ],
        "cnc": [
            "Numerical control",
            "CNC router",
        ],
        "industrial robot": [
            "Industrial robot",
        ],
        "glass bottle": [
            "Glass bottle",
            "Glass production",
        ],
        "pencil": [
            "Pencil",
        ],
        "mechanical keyboard": [
            "Computer keyboard",
            "Keyboard technology",
        ],
        "safety glass": [
            "Safety glass",
            "Tempered glass",
        ],
    }

    def __init__(self) -> None:
        self.wikipedia = WikipediaProvider()
        self.memory = ResearchMemory()
        self.confidence = ResearchConfidenceScorer()

    def research(
        self,
        topic: str,
    ) -> KnowledgePack:

        clean_query = sanitize_topic(
            topic
        )

        cached = self.memory.get(
            clean_query
        )

        if cached is not None:
            print(
                "[EvergreenResearch] HIT -> "
                f"{clean_query}"
            )
            return cached

        print(
            "[EvergreenResearch] MISS -> "
            f"{clean_query}"
        )

        pack = KnowledgePack(
            topic=topic
        )

        queries = self._research_queries(
            clean_query
        )

        all_content: list[str] = []
        seen_urls: set[str] = set()

        for query in queries:

            try:
                results = (
                    self.wikipedia.research(
                        query
                    )
                )
            except Exception as exc:
                print(
                    "[EvergreenResearch] Wikipedia "
                    f"failed for '{query}': {exc}"
                )
                continue

            for result in results:

                url = str(
                    result.get(
                        "url",
                        "",
                    )
                ).strip()

                if url and url in seen_urls:
                    continue

                if url:
                    seen_urls.add(url)

                pack.add_source(
                    result
                )

                content = str(
                    result.get(
                        "content",
                        "",
                    )
                ).strip()

                if content:
                    pack.add_fact(
                        content
                    )
                    all_content.append(
                        content
                    )

            # Two good background sources are enough
            # for the first Rich V1 integration test.
            if len(pack.sources) >= 2:
                break

        if all_content:
            pack.set_summary(
                " ".join(
                    all_content
                )[:6000]
            )

        pack.category = "Evergreen"

        confidence = (
            self.confidence.score(
                clean_query,
                pack.sources,
            )
        )

        pack.score = float(
            confidence.get(
                "score",
                0.0,
            )
            or 0.0
        )

        self.memory.save(
            clean_query,
            pack,
        )

        return pack


    def _research_queries(
        self,
        topic: str,
    ) -> list[str]:
        clean = " ".join(
            str(topic).split()
        ).strip()

        if not clean:
            return []

        lower = clean.lower()

        exact_queries: list[str] = [clean]
        concept_queries: list[str] = []
        alias_queries: list[str] = []

        try:
            concept_queries = list(
                self._expand_concept_queries(clean)
                or []
            )
        except Exception:
            concept_queries = []

        for trigger, aliases in self.RESEARCH_ALIASES.items():
            if trigger in lower:
                alias_queries.extend(
                    str(alias).strip()
                    for alias in aliases
                    if str(alias).strip()
                )

        # The exact premise must remain the highest-priority
        # research request. Previously aliases could replace it
        # completely, which encouraged broad background evidence.
        ordered = (
            exact_queries
            + concept_queries
            + alias_queries
        )

        generic_terms = {
            "film",
            "filmmaking",
            "cinema",
            "technology",
            "science",
            "engineering",
            "business",
            "history",
            "movie",
        }

        topic_tokens = {
            token.strip(
                ".,:;!?()[]{}\"'"
            ).lower()
            for token in clean.split()
            if len(
                token.strip(
                    ".,:;!?()[]{}\"'"
                )
            ) >= 4
        }

        def query_quality(query: str) -> tuple:
            normalized = " ".join(
                str(query).split()
            ).strip()

            tokens = {
                token.strip(
                    ".,:;!?()[]{}\"'"
                ).lower()
                for token in normalized.split()
                if len(
                    token.strip(
                        ".,:;!?()[]{}\"'"
                    )
                ) >= 4
            }

            overlap = len(
                tokens & topic_tokens
            )

            exact = int(
                normalized.lower()
                == clean.lower()
            )

            generic_only = int(
                bool(tokens)
                and tokens.issubset(generic_terms)
            )

            return (
                exact,
                overlap,
                -generic_only,
                min(len(tokens), 12),
            )

        seen: set[str] = set()
        unique: list[str] = []

        for query in ordered:
            normalized = " ".join(
                str(query).split()
            ).strip()

            if not normalized:
                continue

            key = normalized.casefold()

            if key in seen:
                continue

            seen.add(key)
            unique.append(normalized)

        if not unique:
            return [clean]

        exact = unique[0]

        remainder = sorted(
            unique[1:],
            key=query_quality,
            reverse=True,
        )

        # Keep research bounded. Exact premise + up to four
        # supporting concept/alias queries.
        return [exact] + remainder[:4]

    @staticmethod
    def _expand_concept_queries(
        topic: str,
    ) -> list[str]:
        """
        Convert a storytelling hook into a small ordered set
        of encyclopedia-style research concepts.

        Ordering matters:
        specific explanatory concepts come before broad
        background concepts.
        """

        clean = " ".join(
            str(topic).split()
        ).strip()

        if not clean:
            return []

        lower = clean.lower()

        queries: list[str] = []

        def add(value: str) -> None:
            value = " ".join(
                str(value).split()
            ).strip()

            if not value:
                return

            existing = {
                item.casefold()
                for item in queries
            }

            if value.casefold() not in existing:
                queries.append(value)

        # ------------------------------------------
        # High-value explanatory concepts.
        #
        # These are domain concepts, not mappings
        # for one exact YouTube title.
        # ------------------------------------------

        if (
            "time zone" in lower
            or "time zones" in lower
        ):
            add("Time zone")
            add("Standard time")
            add("Railway time")

        if (
            "sell" in lower
            and "loss" in lower
        ):
            add("Loss leader")
            add("Pricing")
            add("Business model")

        if (
            "silence" in lower
            and any(
                term in lower
                for term in (
                    "movie",
                    "film",
                    "scene",
                    "cinema",
                )
            )
        ):
            add("Sound design")
            add("Silence")
            add("Sound film")

        if (
            "train" in lower
            and "wheel" in lower
        ):
            add("Railway wheel")
            add("Wheelset")
            add("Railway wheel flange")

        # ------------------------------------------
        # Broader domain fallbacks.
        # ------------------------------------------

        domain_rules = (
            (
                (
                    "movie",
                    "film",
                    "cinema",
                    "scene",
                ),
                (
                    "Filmmaking",
                    "Film",
                ),
            ),
            (
                (
                    "sound",
                    "audio",
                    "silence",
                ),
                (
                    "Sound design",
                    "Sound",
                ),
            ),
            (
                (
                    "company",
                    "companies",
                    "business",
                    "pricing",
                    "product",
                ),
                (
                    "Business model",
                    "Pricing",
                ),
            ),
            (
                (
                    "train",
                    "railway",
                    "railroad",
                ),
                (
                    "Rail transport",
                    "Railway wheel",
                ),
            ),
            (
                (
                    "time zone",
                    "time zones",
                    "standard time",
                ),
                (
                    "Time zone",
                    "Standard time",
                ),
            ),
            (
                (
                    "airplane",
                    "aircraft",
                    "aviation",
                ),
                (
                    "Aircraft",
                    "Aviation",
                ),
            ),
            (
                (
                    "rocket",
                    "spacecraft",
                ),
                (
                    "Rocket",
                    "Spacecraft",
                ),
            ),
            (
                (
                    "bridge",
                    "skyscraper",
                    "structure",
                ),
                (
                    "Structural engineering",
                ),
            ),
            (
                (
                    "watch",
                    "clock",
                    "timekeeping",
                ),
                (
                    "Horology",
                    "Watch",
                ),
            ),
            (
                (
                    "processor",
                    "computer",
                    "chip",
                    "gpu",
                ),
                (
                    "Computer hardware",
                ),
            ),
        )

        for triggers, concepts in domain_rules:
            if any(
                trigger in lower
                for trigger in triggers
            ):
                for concept in concepts:
                    add(concept)

        # ------------------------------------------
        # Generic keyword fallback.
        # ------------------------------------------

        stop_words = {
            "why",
            "how",
            "what",
            "when",
            "where",
            "which",
            "who",
            "some",
            "certain",
            "many",
            "most",
            "more",
            "less",
            "very",
            "really",
            "can",
            "could",
            "would",
            "should",
            "may",
            "might",
            "make",
            "makes",
            "made",
            "making",
            "become",
            "becomes",
            "became",
            "the",
            "a",
            "an",
            "of",
            "to",
            "from",
            "for",
            "with",
            "without",
            "and",
            "or",
            "in",
            "on",
            "at",
            "by",
            "than",
            "this",
            "that",
            "these",
            "those",

            # Hook-language noise.
            "deliberately",
            "standardized",
            "necessary",
            "different",
            "differently",
            "intense",
            "intensity",
        }

        words = re.findall(
            r"[A-Za-z0-9'-]+",
            clean,
        )

        keywords = [
            word
            for word in words
            if (
                len(word) >= 4
                and word.casefold()
                not in stop_words
            )
        ]

        for word in keywords:
            add(word.title())

            if len(queries) >= 6:
                break

        # Original hook remains the final fallback only.
        add(clean)

        return queries[:6]

    @staticmethod
    def build_research_text(
        pack: KnowledgePack,
    ) -> str:

        parts: list[str] = []

        if pack.summary:
            parts.append(
                pack.summary.strip()
            )

        for fact in pack.facts:

            clean = str(
                fact
            ).strip()

            if (
                clean
                and clean not in parts
            ):
                parts.append(clean)

        return "\n\n".join(parts)
