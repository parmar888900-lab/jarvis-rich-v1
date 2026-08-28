from dataclasses import dataclass


@dataclass
class GeneratedImage:
    prompt: str
    image_path: str
    provider: str
    width: int
    height: int