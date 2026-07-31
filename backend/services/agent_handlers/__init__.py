"""Built-in agent handlers. Add new handler files here to register agents."""

from services.agent_handlers.base import BaseAgentHandler
from services.agent_handlers.youtube import YoutubeAgentHandler

BUILTIN_HANDLERS: list[type[BaseAgentHandler]] = [
    YoutubeAgentHandler,
]

__all__ = ["BaseAgentHandler", "BUILTIN_HANDLERS", "YoutubeAgentHandler"]
