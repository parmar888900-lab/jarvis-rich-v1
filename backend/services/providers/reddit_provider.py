"""Reddit trend discovery provider."""

from backend.services.reddit_service import RedditService

from .base import TrendProvider


class RedditProvider(TrendProvider):
    """Discover high-engagement Reddit topics."""

    DEFAULT_SUBREDDITS = (
        "AskReddit",
        "todayilearned",
        "technology",
    )

    def __init__(
        self,
        subreddits: tuple[str, ...] | None = None,
    ):
        self.service = RedditService()
        self.subreddits = (
            subreddits
            or self.DEFAULT_SUBREDDITS
        )

    @property
    def name(self) -> str:
        return "Reddit"

    def get_trends(
        self,
        limit: int = 10,
    ) -> list[dict]:
        if limit <= 0:
            return []

        candidates = []

        per_subreddit = max(
            5,
            min(limit, 15),
        )

        for subreddit in self.subreddits:
            try:
                posts = self.service.get_top_posts(
                    subreddit=subreddit,
                    limit=per_subreddit,
                )

            except Exception as exc:
                print(
                    f"[RedditProvider] "
                    f"r/{subreddit} failed: {exc}"
                )
                continue

            for post in posts:
                upvotes = int(
                    post.get("score", 0) or 0
                )
                comments = int(
                    post.get("comments", 0) or 0
                )

                # Normalize Reddit engagement so one
                # provider cannot dominate purely
                # because it uses larger raw numbers.
                opportunity_score = min(
                    (upvotes / 500.0)
                    + (comments / 100.0),
                    100.0,
                )

                candidates.append(
                    {
                        "title": post.get(
                            "title",
                            "",
                        ),
                        "source": "Reddit",
                        "score": round(
                            opportunity_score,
                            2,
                        ),
                        "category": subreddit,
                        "url": post.get(
                            "url",
                            "",
                        ),
                        "description": post.get(
                            "body",
                            "",
                        ),
                        "upvotes": upvotes,
                        "comments": comments,
                        "subreddit": subreddit,
                    }
                )

        candidates = [
            trend
            for trend in candidates
            if trend["title"]
        ]

        candidates.sort(
            key=lambda trend: trend["score"],
            reverse=True,
        )

        print(
            f"[RedditProvider] Retrieved "
            f"{len(candidates)} candidates"
        )

        return candidates[:limit]
