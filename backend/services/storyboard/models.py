from dataclasses import dataclass


@dataclass
class Scene:
    narration: str
    image_prompt: str
    duration: float