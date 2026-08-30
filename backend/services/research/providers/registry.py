"""Research provider registry."""

from .base import ResearchProvider


class ResearchRegistry:
    """
    Holds all registered research providers.
    """

    def __init__(self):
        self.providers: list[ResearchProvider] = []

    def register(self, provider: ResearchProvider):
        self.providers.append(provider)

    def get_all(self):
        return self.providers