"""Google News RSS trend provider."""

from urllib.request import Request, urlopen
from xml.etree import ElementTree

from .base import TrendProvider


class RSSProvider(TrendProvider):
    """Fetch trending news from Google News RSS."""

    @property
    def name(self) -> str:
        return "Google News RSS"

    def get_trends(self, limit: int = 10):
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
            with urlopen(request, timeout=15) as response:
                xml_data = response.read()

            root = ElementTree.fromstring(xml_data)

        except Exception as e:
            print(f"[RSSProvider] Failed to fetch Google News RSS: {e}")
            return []

        trends = []

        for index, item in enumerate(root.findall(".//item")):
            if index >= limit:
                break

            title_element = item.find("title")
            link_element = item.find("link")
            description_element = item.find("description")

            title = (
                title_element.text.strip()
                if title_element is not None and title_element.text
                else ""
            )

            link = (
                link_element.text.strip()
                if link_element is not None and link_element.text
                else ""
            )

            description = (
                description_element.text.strip()
                if description_element is not None
                and description_element.text
                else ""
            )

            if not title:
                continue

            trends.append(
                {
                    "title": title,
                    "source": "Google News RSS",
                    "score": 80 - index,
                    "category": "News",
                    "url": link,
                    "description": description,
                }
            )

        print(
            f"[RSSProvider] Retrieved {len(trends)} Google News trends"
        )

        return trends