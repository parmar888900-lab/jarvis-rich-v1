from .trend_manager import TrendManager
from .youtube_provider import YoutubeProvider
from .rss_provider import RSSProvider


def build_trend_manager() -> TrendManager:
    manager = TrendManager()

    # YouTube Trending
    manager.register(YoutubeProvider())

    # Google News RSS
    manager.register(RSSProvider())

    return manager