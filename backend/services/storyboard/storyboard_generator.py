"""
Converts GeneratedContent into a storyboard.
"""

from typing import List

from backend.models.generated_content import GeneratedContent
from backend.services.storyboard.scene import Scene
from backend.services.storyboard.prompt_builder import PromptBuilder


class StoryboardGenerator:
    """
    Converts a generated script into a list of Scene objects.

    Every downstream service uses these scenes.

    Image Generator
    Voice Generator
    Subtitle Generator
    Renderer
    """

    DEFAULT_SCENE_DURATION = 4.5

    def __init__(self):
        self.prompt_builder = PromptBuilder()

    def generate(
        self,
        content: GeneratedContent,
    ) -> List[Scene]:

        scenes: List[Scene] = []

        current_time = 0.0

        transitions = [
            "cut",
            "flash",
            "fade",
            "zoom",
        ]

        camera_moves = [
            "slow_zoom",
            "push_in",
            "pan_left",
            "pan_right",
            "tilt_up",
            "tilt_down",
        ]

        for i, line in enumerate(content.script_lines):

            duration = self.DEFAULT_SCENE_DURATION

            scene = Scene(
                number=i + 1,
                narration=line,
                subtitle=line,
                duration=duration,
                image_prompt="",
                camera_motion=camera_moves[i % len(camera_moves)],
                transition=transitions[i % len(transitions)],
            )

            scene.start_time = current_time
            scene.end_time = current_time + duration

            scene.image_prompt = self.prompt_builder.build(
                content,
                scene,
            )

            scenes.append(scene)

            current_time += duration

        return scenes