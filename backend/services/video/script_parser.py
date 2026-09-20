"""Converts a generated script into timed scenes."""

from dataclasses import dataclass


@dataclass
class Scene:
    start: float
    end: float
    text: str


class ScriptParser:
    """
    Splits a YouTube script into timed scenes.

    Current implementation:
    - sentence based
    - fixed duration

    Future:
    - AI scene detection
    - pacing
    - emotion
    """

    def parse(
        self,
        script: str,
        seconds_per_scene: float = 4.0,
    ) -> list[Scene]:

        script = script.strip()

        if not script:
            return []

        parts = [
            s.strip()
            for s in script.replace("\n", " ").split(".")
            if s.strip()
        ]

        scenes = []

        current = 0.0

        for part in parts:

            scenes.append(
                Scene(
                    start=current,
                    end=current + seconds_per_scene,
                    text=part + ".",
                )
            )

            current += seconds_per_scene

        return scenes