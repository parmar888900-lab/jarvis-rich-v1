from dataclasses import dataclass


@dataclass(slots=True)
class Scene:
    """
    Represents one storyboard scene.
    """

    narration: str

    image_prompt: str

    duration: float = 4.0

    start_time: float = 0.0

    end_time: float = 0.0
