import requests

from backend.config import settings
from .base import TrendProvider


class YoutubeProvider(TrendProvider):
    @property
    def name(self) -> str:
        return "YouTube"

    def get_trends(self, limit: int = 10):
        url = "https://www.googleapis.com/youtube/v3/videos"

        params = {
            "part": "snippet,statistics",
            "chart": "mostPopular",
            "regionCode": "IN",
            "maxResults": limit,
            "key": settings.youtube_api_key,
        }

        response = requests.get(
            url,
            params=params,
            timeout=20,
        )

        response.raise_for_status()

        data = response.json()

        trends = []

        for item in data.get("items", []):
            snippet = item["snippet"]
            statistics = item.get("statistics", {})

            views = int(statistics.get("viewCount", 0))
            likes = int(statistics.get("likeCount", 0))

            score = views // 100000 + likes // 1000

            trends.append(
                {
                    "title": snippet["title"],
                    "source": "YouTube",
                    "score": score,
                    "category": snippet.get("categoryId", "Unknown"),
                    "url": f"https://www.youtube.com/watch?v={item['id']}",
                    "channel": snippet["channelTitle"],
                    "published": snippet["publishedAt"],
                    "views": views,
                    "likes": likes,
                }
            )

        trends.sort(
            key=lambda trend: trend["score"],
            reverse=True,
        )

        return trends[:limit]