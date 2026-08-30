"""Google News research provider."""

from html import unescape
from urllib.parse import quote_plus
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

    def research(
        self,
        topic: str,
    ) -> list[dict]:
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
            with urlopen(
                request,
                timeout=15,
            ) as response:
                xml_data = response.read()

            root = ElementTree.fromstring(
                xml_data
            )

        except Exception as exc:
            print(
                f"[NewsProvider] Failed to research "
                f"'{topic}': {exc}"
            )
            return []

        results = []

        for item in root.findall(".//item"):
            title = self._text(
                item.find("title")
            )
            link = self._text(
                item.find("link")
            )
            description = self._clean_text(
                self._text(
                    item.find("description")
                )
            )
            published = self._text(
                item.find("pubDate")
            )

            if not title:
                continue

            publisher = self._extract_publisher(
                title
            )

            headline = self._extract_headline(
                title
            )

            content_parts = []

            if description:
                content_parts.append(description)

            if published:
                content_parts.append(
                    f"Published: {published}"
                )

            results.append(
                {
                    "title": headline,
                    "content": "\n".join(
                        content_parts
                    ),
                    "source": "Google News",
                    "publisher": publisher,
                    "url": link,
                    "published": published,
                    "confidence": 0.80,
                }
            )

            if len(results) >= 5:
                break

        print(
            f"[NewsProvider] Retrieved "
            f"{len(results)} research results "
            f"for '{topic}'"
        )

        return results

    @staticmethod
    def _text(element) -> str:
        if (
            element is None
            or not element.text
        ):
            return ""

        return element.text.strip()

    @staticmethod
    def _clean_text(
        value: str,
    ) -> str:
        if not value:
            return ""

        return unescape(value).strip()

    @staticmethod
    def _extract_publisher(
        title: str,
    ) -> str:
        if " - " not in title:
            return ""

        return title.rsplit(
            " - ",
            1,
        )[1].strip()

    @staticmethod
    def _extract_headline(
        title: str,
    ) -> str:
        if " - " not in title:
            return title.strip()

        return title.rsplit(
            " - ",
            1,
        )[0].strip()

    @staticmethod
    def _encode_query(
        value: str,
    ) -> str:
        return quote_plus(
            value.strip()
        )
