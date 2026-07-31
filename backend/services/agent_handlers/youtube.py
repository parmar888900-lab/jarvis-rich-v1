"""YouTube agent handler — stub for Phase 2."""

from services.agent_handlers.base import BaseAgentHandler


class YoutubeAgentHandler(BaseAgentHandler):
    name = "youtube"
    supported_tasks = frozenset({"create_video", "upload_video", "analyze_trends"})

    async def execute(self, task: str, command_id: str, **kwargs) -> dict:
        return {
            "agent": self.name,
            "task": task,
            "command_id": command_id,
            "message": f"YouTube agent received task '{task}' (stub — implement in Phase 3)",
        }
