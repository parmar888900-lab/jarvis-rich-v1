"""Abstract base class for all agent handlers."""

from abc import ABC, abstractmethod


class BaseAgentHandler(ABC):
    """Every agent must subclass this and register with AgentRegistry."""

    name: str
    supported_tasks: frozenset[str]

    @abstractmethod
    async def execute(self, task: str, command_id: str, **kwargs) -> dict:
        """Run the requested task and return a result dict."""

    def supports_task(self, task: str) -> bool:
        return task in self.supported_tasks
