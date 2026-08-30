"""Knowledge Pack models."""

from dataclasses import dataclass, field


@dataclass
class KnowledgePack:
    """
    Structured research object passed through Jarvis.
    """

    topic: str

    summary: str = ""

    facts: list[str] = field(default_factory=list)

    keywords: list[str] = field(default_factory=list)

    sources: list[dict] = field(default_factory=list)

    score: float = 0.0

    category: str = "Unknown"

    def add_fact(self, fact: str):
        if fact and fact not in self.facts:
            self.facts.append(fact)

    def add_keyword(self, keyword: str):
        if keyword and keyword not in self.keywords:
            self.keywords.append(keyword)

    def add_source(self, source: dict):
        if source:
            self.sources.append(source)

    def set_summary(self, summary: str):
        if summary:
            self.summary = summary.strip()

    def to_dict(self) -> dict:
        return {
            "topic": self.topic,
            "summary": self.summary,
            "facts": self.facts,
            "keywords": self.keywords,
            "sources": self.sources,
            "score": self.score,
            "category": self.category,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "KnowledgePack":
        """
        Reconstruct a KnowledgePack from cached or serialized data.
        """

        return cls(
            topic=data.get("topic", ""),
            summary=data.get("summary", ""),
            facts=list(data.get("facts", [])),
            keywords=list(data.get("keywords", [])),
            sources=list(data.get("sources", [])),
            score=float(data.get("score", 0.0)),
            category=data.get("category", "Unknown"),
        )