"""YouTube agent handler."""

from backend.services.agent_handlers.base import BaseAgentHandler
from backend.services.llm_service import LLMService
from backend.services.reddit_service import RedditService


class YoutubeAgentHandler(BaseAgentHandler):
    name = "youtube"
    supported_tasks = frozenset(
        {
            "create_video",
            "upload_video",
            "analyze_trends",
        }
    )

    async def execute(self, task: str, command_id: str, **kwargs) -> dict:
        if task != "create_video":
            return {
                "agent": self.name,
                "task": task,
                "command_id": command_id,
                "message": "Task not implemented yet.",
            }

        llm = LLMService()
        reddit = RedditService()

        posts = reddit.get_top_posts(limit=25)

        best_post = max(
            posts,
            key=lambda p: p["score"] + (p["comments"] * 5)
        )

        messages = [
            {
                "role": "system",
                "content": (
                    "You are one of the world's best YouTube Shorts writers. "
                    "You specialize in transforming REAL Reddit stories into "
                    "high-retention viral YouTube Shorts. "
                    "Never invent major events that did not happen."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Here is a REAL Reddit post.\n\n"
                    f"Title: {best_post['title']}\n\n"
                    f"Story:\n{best_post['body']}\n\n"

                    "Rewrite this into an addictive 45-60 second YouTube Shorts.\n\n"

                    "Rules:\n"
                    "- Keep the facts true.\n"
                    "- Do not invent major events.\n"
                    "- Hook the viewer in the first sentence.\n"
                    "- Build suspense every few seconds.\n"
                    "- Make it conversational.\n"
                    "- End with a question that encourages comments.\n\n"

                    "Return EXACTLY this format:\n\n"

                    "TITLE:\n"
                    "<title>\n\n"

                    "SCRIPT:\n"
                    "<script>\n\n"

                    "DESCRIPTION:\n"
                    "<description>\n\n"

                    "HASHTAGS:\n"
                    "<hashtags>"
                ),
            },
        ]

        response = await llm.chat(messages)

        title = ""
        script = ""
        description = ""
        hashtags = ""

        current = None

        for line in response.splitlines():
            text = line.strip()

            if text == "TITLE:":
                current = "title"
                continue

            if text == "SCRIPT:":
                current = "script"
                continue

            if text == "DESCRIPTION:":
                current = "description"
                continue

            if text == "HASHTAGS:":
                current = "hashtags"
                continue

            if current == "title":
                title += line + "\n"
            elif current == "script":
                script += line + "\n"
            elif current == "description":
                description += line + "\n"
            elif current == "hashtags":
                hashtags += line + "\n"

        return {
            "agent": self.name,
            "task": task,
            "command_id": command_id,
            "title": title.strip(),
            "script": script.strip(),
            "description": description.strip(),
            "hashtags": hashtags.strip(),
            "reddit_title": best_post["title"],
            "reddit_score": best_post["score"],
            "reddit_comments": best_post["comments"],
            "reddit_url": best_post["url"],
        }