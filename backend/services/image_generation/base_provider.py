from abc import ABC, abstractmethod

from backend.services.image_generation.models import GeneratedImage


class BaseImageProvider(ABC):

    @abstractmethod
    async def generate(
        self,
        prompt: str,
    ) -> GeneratedImage:
        ...