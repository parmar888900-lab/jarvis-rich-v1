"""Visual search-query generation for Jarvis Rich V1."""

from __future__ import annotations

import re


class MediaQueryBuilder:
    """
    Convert narration and topic context into concrete visual-search
    queries suitable for licensed-media libraries.

    The goal is not to summarize narration. The goal is to identify
    physical objects, places, people, machines, components, or scenes
    that can actually exist as searchable media.
    """

    STOPWORDS = {
        "a", "an", "and", "are", "as", "at", "be", "because",
        "been", "being", "but", "by", "can", "could", "did",
        "do", "does", "for", "from", "had", "has", "have",
        "how", "if", "in", "into", "is", "it", "its", "more",
        "most", "of", "on", "or", "our", "so", "that", "the",
        "their", "them", "these", "they", "this", "those", "to",
        "was", "were", "what", "when", "where", "which", "while",
        "who", "why", "will", "with", "without", "you", "your",
        "different", "differently", "actually", "really", "know",
        "helps", "help", "keep", "keeps", "unique", "design",
        "designed", "works", "work", "working", "special",
    }

    TOPIC_VISUAL_ALIASES = {
        "train wheel": [
            "railway wheelset",
            "train wheel rail",
            "railway wheel flange",
            "railroad wheel profile",
            "train bogie wheels",
            "railway wheels close up",
        ],
        "airplane window": [
            "aircraft passenger window",
            "airplane fuselage windows",
            "rounded aircraft window",
            "aircraft cabin window",
        ],
        "suspension bridge": [
            "suspension bridge cables",
            "bridge tower cables",
            "suspension bridge structure",
            "bridge engineering",
        ],
        "skyscraper": [
            "skyscraper structure",
            "tall building engineering",
            "skyscraper construction",
            "building tuned mass damper",
        ],
        "black box": [
            "aircraft flight recorder",
            "airplane black box",
            "flight data recorder",
            "cockpit voice recorder",
        ],
        "rocket": [
            "rocket launch",
            "space rocket engine",
            "rocket launch pad",
            "rocket propulsion",
        ],
        "satellite": [
            "satellite orbit earth",
            "communications satellite",
            "space satellite",
            "satellite solar panels",
        ],
        "gps": [
            "GPS satellite",
            "navigation satellite",
            "GPS receiver",
            "satellite navigation",
        ],
        "mechanical watch": [
            "mechanical watch movement",
            "luxury watch gears",
            "watchmaker movement",
            "mechanical wristwatch",
        ],
        "private jet": [
            "private jet aircraft",
            "business jet cabin",
            "private aircraft",
            "business jet airport",
        ],
        "supercar": [
            "supercar factory",
            "sports car assembly",
            "luxury sports car",
            "automotive manufacturing",
        ],
        "data center": [
            "data center servers",
            "server racks cooling",
            "data center cooling",
            "computer server room",
        ],
        "noise cancelling": [
            "noise cancelling headphones",
            "headphones microphone",
            "audio waveform headphones",
        ],
        "green screen": [
            "film green screen studio",
            "chroma key filming",
            "movie green screen set",
        ],
        "shipping container": [
            "shipping containers port",
            "container ship cargo",
            "freight containers",
            "shipping container terminal",
        ],
        "barcode": [
            "barcode scanner",
            "product barcode",
            "supermarket barcode scanner",
        ],
        "elevator": [
            "elevator machinery",
            "elevator shaft",
            "lift motor mechanism",
        ],
        "cnc": [
            "CNC machine metal cutting",
            "CNC milling machine",
            "computer numerical control machine",
        ],
        "industrial robot": [
            "industrial robot factory",
            "robotic car assembly",
            "factory robot arm",
        ],
        "glass bottle": [
            "glass bottle factory",
            "glass bottle manufacturing",
            "bottle production line",
        ],
        "pencil": [
            "pencil manufacturing",
            "wooden pencils",
            "hexagonal pencil",
        ],
        "mechanical keyboard": [
            "mechanical keyboard switch",
            "keyboard switch close up",
            "mechanical keyboard",
        ],
        "safety glass": [
            "tempered safety glass",
            "broken tempered glass",
            "automotive safety glass",
        ],
    }

    @classmethod
    def build(
        cls,
        *,
        topic: str,
        genre: str,
        narration: str,
    ) -> list[str]:

        topic_lower = topic.lower()

        alias_queries: list[str] = []

        for trigger, queries in (
            cls.TOPIC_VISUAL_ALIASES.items()
        ):
            if trigger in topic_lower:
                alias_queries.extend(queries)

        topic_words = cls._keywords(
            topic,
            limit=6,
        )

        narration_words = cls._keywords(
            narration,
            limit=6,
        )

        object_query = cls._object_query(
            topic_words
        )

        narration_query = cls._object_query(
            narration_words
        )

        candidates = [
            *alias_queries,
            object_query,
            narration_query,
            " ".join(topic_words[:3]),
            " ".join(narration_words[:3]),
        ]

        output: list[str] = []
        seen: set[str] = set()

        for query in candidates:

            query = " ".join(
                str(query).split()
            ).strip()

            if len(query) < 3:
                continue

            key = query.lower()

            if key in seen:
                continue

            seen.add(key)
            output.append(query)

        return output[:10]

    @classmethod
    def _keywords(
        cls,
        text: str,
        *,
        limit: int,
    ) -> list[str]:

        words = re.findall(
            r"[A-Za-z0-9]+",
            text.lower(),
        )

        output: list[str] = []

        for word in words:

            if (
                len(word) < 3
                or word in cls.STOPWORDS
            ):
                continue

            if word not in output:
                output.append(word)

            if len(output) >= limit:
                break

        return output

    @staticmethod
    def _object_query(
        words: list[str],
    ) -> str:

        if not words:
            return ""

        return " ".join(
            words[:4]
        )
