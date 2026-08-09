import requests


class RedditService:
    BASE_URL = "https://www.reddit.com"

    HEADERS = {
        "User-Agent": "JarvisAI/1.0"
    }

    def get_top_posts(self, subreddit="AskReddit", limit=25):
        url = f"{self.BASE_URL}/r/{subreddit}/top.json?t=day&limit={limit}"

        response = requests.get(
            url,
            headers=self.HEADERS,
            timeout=15,
        )

        response.raise_for_status()

        posts = []

        for child in response.json()["data"]["children"]:
            data = child["data"]

            if data.get("stickied"):
                continue

            if data.get("over_18"):
                continue

            posts.append({
                "title": data["title"],
                "body": data.get("selftext", ""),
                "score": data["score"],
                "comments": data["num_comments"],
                "url": "https://reddit.com" + data["permalink"],
            })

        return posts