"""Google News RSS trend provider."""

from datetime import timezone
from email.utils import parsedate_to_datetime
from urllib.request import Request, urlopen
from xml.etree import ElementTree

from .base import TrendProvider


class RSSProvider(TrendProvider):
    """Fetch trending news from Google News RSS."""

    @property
    def name(self) -> str:
        return "Google News RSS"

    def get_trends(
        self,
        limit: int = 10,
    ) -> list[dict]:
        url = (
            "https://news.google.com/rss"
            "?hl=en-IN"
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
                "[RSSProvider] Failed to fetch "
                f"Google News RSS: {exc}"
            )
            return []

        trends = []

        for index, item in enumerate(
            root.findall(".//item")
        ):
            if index >= limit:
                break

            title = self._text(
                item,
                "title",
            )
            link = self._text(
                item,
                "link",
            )
            description = self._text(
                item,
                "description",
            )
            pub_date = self._text(
                item,
                "pubDate",
            )

            if not title:
                continue

            published = self._parse_published(
                pub_date
            )

            publisher = self._extract_publisher(
                title
            )

            trends.append(
                {
                    "title": title,
                    "source": "Google News RSS",
                    "score": 80 - index,
                    "category": "News",
                    "url": link,
                    "description": description,
                    "published": published,
                    "publisher": publisher,
                }
            )

        print(
            f"[RSSProvider] Retrieved "
            f"{len(trends)} Google News trends"
        )

        return trends

    @staticmethod
    def _text(
        item,
        tag: str,
    ) -> str:
        element = item.find(tag)

        if (
            element is None
            or not element.text
        ):
            return ""

        return element.text.strip()

    @staticmethod
    def _parse_published(
        value: str,
    ) -> str:
        """Convert RSS pubDate to UTC ISO-8601."""

        if not value:
            return ""

        try:
            published = parsedate_to_datetime(
                value
            )

            if published.tzinfo is None:
                published = published.replace(
                    tzinfo=timezone.utc
                )
            else:
                published = (
                    published.astimezone(
                        timezone.utc
                    )
                )

            return published.isoformat()

        except (TypeError, ValueError):
            return ""

    @staticmethod
    def _extract_publisher(
        title: str,
    ) -> str:
        """
        Extract the publisher from Google's
        common 'headline - publisher' format.
        """

        if " - " not in title:
            return ""

        return title.rsplit(
            " - ",
            1,
        )[1].strip()
