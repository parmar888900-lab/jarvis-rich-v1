"""Built-in agent handlers. Add new handler files here to register agents."""

from backend.services.agent_handlers.base import BaseAgentHandler
from backend.services.agent_handlers.goal import GoalAgentHandler
from backend.services.agent_handlers.youtube import YoutubeAgentHandler

BUILTIN_HANDLERS: list[type[BaseAgentHandler]] = [
    YoutubeAgentHandler,
    GoalAgentHandler,
]

__all__ = [
    "BaseAgentHandler",
    "BUILTIN_HANDLERS",
    "GoalAgentHandler",
    "YoutubeAgentHandler",
]
