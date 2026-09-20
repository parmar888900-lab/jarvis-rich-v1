"""Official NASA Images metadata research provider."""

from __future__ import annotations

import requests

from .base import ResearchProvider


class NasaImagesResearchProvider(ResearchProvider):
    """Use NASA's public media descriptions as grounded evidence."""

    SEARCH_URL = "https://images-api.nasa.gov/search"

    @property
    def name(self) -> str:
        return "NASA Images"

    def research(self, topic: str) -> list[dict]:
        query = " ".join(str(topic).split()).strip()
        if not query:
            return []

        response = requests.get(
            self.SEARCH_URL,
            params={
                "q": query,
                "media_type": "video",
                "page_size": 5,
            },
            headers={"User-Agent": "JarvisRichV1/0.1 evidence research"},
            timeout=20,
        )
        response.raise_for_status()

        items = (
            response.json()
            .get("collection", {})
            .get("items", [])
            or []
        )

        for item in items:
            rows = item.get("data", []) or []
            if not rows:
                continue

            metadata = rows[0]
            nasa_id = str(metadata.get("nasa_id", "")).strip()
            description = " ".join(
                str(metadata.get("description", "")).split()
            ).strip()
            title = " ".join(
                str(metadata.get("title", nasa_id)).split()
            ).strip()

            if not nasa_id or not description:
                continue

            return [
                {
                    "title": title or nasa_id,
                    "content": description[:3000],
                    "source": self.name,
                    "url": f"https://images.nasa.gov/details/{nasa_id}",
                    "confidence": 0.98,
                }
            ]

        return []
