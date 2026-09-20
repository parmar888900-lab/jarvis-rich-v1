"""Central registry for routing commands to agent handlers.

Designed to scale to 100+ agents — register new handlers without
modifying Commander logic.
"""

import logging

from backend.services.agent_handlers import BUILTIN_HANDLERS
from backend.services.agent_handlers.base import BaseAgentHandler

logger = logging.getLogger("jarvis.commander.registry")


class AgentNotFoundError(Exception):
    def __init__(self, agent: str):
        self.agent = agent
        super().__init__(f"Agent '{agent}' is not registered")


class TaskNotSupportedError(Exception):
    def __init__(self, agent: str, task: str, supported: frozenset[str]):
        self.agent = agent
        self.task = task
        self.supported = supported
        super().__init__(
            f"Agent '{agent}' does not support task '{task}'. "
            f"Supported: {', '.join(sorted(supported)) or 'none'}"
        )


class AgentRegistry:
    """Maps agent name → handler instance."""

    def __init__(self) -> None:
        self._handlers: dict[str, BaseAgentHandler] = {}

    def register(self, handler: BaseAgentHandler) -> None:
        name = handler.name.lower()
        if name in self._handlers:
            logger.warning("Overwriting handler for agent '%s'", name)
        self._handlers[name] = handler
        logger.info("Registered agent handler: %s (tasks: %s)", name, sorted(handler.supported_tasks))

    def register_class(self, handler_cls: type[BaseAgentHandler]) -> None:
        self.register(handler_cls())

    def get(self, agent: str) -> BaseAgentHandler:
        handler = self._handlers.get(agent.lower())
        if handler is None:
            raise AgentNotFoundError(agent)
        return handler

    def list_agents(self) -> list[str]:
        return sorted(self._handlers.keys())

    def is_registered(self, agent: str) -> bool:
        return agent.lower() in self._handlers


def build_default_registry() -> AgentRegistry:
    """Create a registry pre-loaded with all built-in handlers."""
    registry = AgentRegistry()
    for handler_cls in BUILTIN_HANDLERS:
        registry.register_class(handler_cls)
    return registry
