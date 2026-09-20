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
            user_agent=(
                "JarvisRichV1/0.1 "
                "(https://github.com/parmar888900-lab/jarvis-rich-v1; evidence research)"
            ),
            timeout=20,
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
