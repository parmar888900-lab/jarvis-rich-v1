"""Google News research provider."""

from html import unescape
from urllib.request import Request, urlopen
from xml.etree import ElementTree

from .base import ResearchProvider


class NewsProvider(ResearchProvider):
    """
    Research provider using Google News RSS.

    This is separate from the trend RSS provider because its job is
    to gather research material rather than rank trends.
    """

    @property
    def name(self) -> str:
        return "Google News Research"

    def research(self, topic: str) -> list[dict]:
        if not topic or not topic.strip():
            return []

        url = (
            "https://news.google.com/rss/search"
            f"?q={self._encode_query(topic)}"
            "&hl=en-IN"
            "&gl=IN"
            "&ceid=IN:en"
        )

        request = Request(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 "
                    "(Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 "
                    "(KHTML, like Gecko) "
                    "Chrome/131.0 Safari/537.36"
                )
            },
        )

        try:
            with urlopen(request, timeout=15) as response:
                xml_data = response.read()

            root = ElementTree.fromstring(xml_data)

        except Exception as exc:
            print(
                f"[NewsProvider] Failed to research "
                f"'{topic}': {exc}"
            )
            return []

        results = []

        for item in root.findall(".//item"):
            title_element = item.find("title")
            link_element = item.find("link")
            description_element = item.find("description")
            pub_date_element = item.find("pubDate")

            title = self._text(title_element)
            link = self._text(link_element)
            description = self._clean_text(
                self._text(description_element)
            )
            published = self._text(pub_date_element)

            if not title:
                continue

            content_parts = []

            if description:
                content_parts.append(description)

            if published:
                content_parts.append(
                    f"Published: {published}"
                )

            content = "\n".join(content_parts)

            results.append(
                {
                    "title": title,
                    "content": content,
                    "source": "Google News",
                    "url": link,
                    "published": published,
                    "confidence": 0.80,
                }
            )

            if len(results) >= 5:
                break

        print(
            f"[NewsProvider] Retrieved "
            f"{len(results)} research results for '{topic}'"
        )

        return results

    @staticmethod
    def _text(element) -> str:
        if element is None or not element.text:
            return ""

        return element.text.strip()

    @staticmethod
    def _clean_text(value: str) -> str:
        if not value:
            return ""

        return unescape(value).strip()

    @staticmethod
    def _encode_query(value: str) -> str:
        from urllib.parse import quote_plus

        return quote_plus(value.strip())