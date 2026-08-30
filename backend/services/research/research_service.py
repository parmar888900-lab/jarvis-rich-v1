"""Research service with automated topic sanitization and research memory."""

import re

from backend.services.research.confidence import ResearchConfidenceScorer
from backend.services.research.knowledge_pack import KnowledgePack
from backend.services.research.providers.news import NewsProvider
from backend.services.research.providers.registry import ResearchRegistry
from backend.services.research.providers.wikipedia import WikipediaProvider
from backend.services.research.research_memory import ResearchMemory


def sanitize_topic(raw_title: str) -> str:
    """
    Extract the core topic from noisy titles for better research quality.
    """

    if not raw_title:
        return ""

    segments = re.split(r"[|\-–—]", raw_title)
    clean = segments[0] if segments else raw_title

    noise_patterns = [
        r"\b(official|teaser|trailer|hd|video|full movie|breaking news|live)\b",
        r"\b(ndtv|live law|the hindu|times of india|hindustan times)\b",
        r"\b(\d{1,2}(st|nd|rd|th)?\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec))\b",
        r"\b202\d\b",
    ]

    for pattern in noise_patterns:
        clean = re.sub(
            pattern,
            "",
            clean,
            flags=re.IGNORECASE,
        )

    clean = re.sub(r"\s+", " ", clean).strip()

    return clean if len(clean) >= 3 else raw_title.strip()


class ResearchService:
    """
    Collects research from all providers and produces a KnowledgePack.

    Responsibilities:
        - Topic sanitization
        - Research provider orchestration
        - KnowledgePack construction
        - Temporary research memory
        - Topic classification
    """

    def __init__(self):
        self.registry = ResearchRegistry()

        # Background knowledge
        self.registry.register(WikipediaProvider())

        # Current events
        self.registry.register(NewsProvider())

        # Research memory (RAM for now, SQLite later)
        self.memory = ResearchMemory()
        self.confidence = ResearchConfidenceScorer()

    def research(self, topic: str) -> KnowledgePack:
        """
        Research a topic and return a populated KnowledgePack.
        """

        clean_query = sanitize_topic(topic)

        cached = self.memory.get(clean_query)

        if cached is not None:
            print(f"[ResearchMemory] HIT -> {clean_query}")
            return cached

        print(f"[ResearchMemory] MISS -> {clean_query}")

        pack = KnowledgePack(topic=topic)

        all_content = []

        for provider in self.registry.get_all():

            try:
                results = provider.research(clean_query)

                for result in results:

                    pack.add_source(result)

                    content = result.get("content", "").strip()

                    if content:
                        pack.add_fact(content)
                        all_content.append(content)

            except Exception as exc:

                print(
                    f"[ResearchService] "
                    f"{provider.name} failed for "
                    f"'{clean_query}': {exc}"
                )

        # Summary
        if all_content:
            pack.set_summary(
                " ".join(all_content[:3])[:4000]
            )

        # Category
        pack.category = self._classify_topic(clean_query)

        # Deterministic research confidence.
        confidence = self.confidence.score(
            clean_query,
            pack.sources,
        )

        pack.score = confidence["score"]

        # Save for future requests
        self.memory.save(
            clean_query,
            pack,
        )

        return pack

    @staticmethod
    def _classify_topic(topic: str) -> str:

        text = topic.lower()

        news_keywords = {
            "news",
            "live",
            "breaking",
            "parliament",
            "government",
            "election",
            "protest",
            "war",
            "match",
            "championship",
            "cup",
            "trailer",
            "teaser",
            "movie",
            "gaming",
            "esports",
        }

        if any(keyword in text for keyword in news_keywords):
            return "News"

        return "General"

    @staticmethod
    def _calculate_research_score(pack: KnowledgePack) -> float:
        """
        Simple research quality score.

        This will later evolve into Jarvis'
        research confidence system.
        """

        score = 0.0

        score += min(len(pack.sources) * 2.0, 20.0)

        score += min(len(pack.facts), 10)

        if pack.summary:
            score += 10

        return round(score, 2)