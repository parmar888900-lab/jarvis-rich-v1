"""Wikipedia research provider."""

import wikipediaapi

from .base import ResearchProvider


class WikipediaProvider(ResearchProvider):
    @property
    def name(self) -> str:
        return "Wikipedia"

    def __init__(self):
        self.wiki = wikipediaapi.Wikipedia(
            language="en",
            user_agent="JarvisAI/1.0 (research bot)"
        )

    def research(self, topic: str) -> list[dict]:
        page = self.wiki.page(topic)

        if not page.exists():
            return []

        return [
            {
                "title": page.title,
                "content": page.summary[:3000],
                "source": "Wikipedia",
                "url": page.fullurl,
                "confidence": 0.95,
            }
        ]