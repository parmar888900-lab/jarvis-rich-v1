from backend.models.generated_content import GeneratedContent
from backend.services.storyboard.scene import Scene


class StoryboardGenerator:
    """
    Converts GeneratedContent into storyboard scenes.
    """

    def generate(
        self,
        content: GeneratedContent,
    ) -> list[Scene]:

        scenes = []

        for line in content.script_lines:

            scenes.append(
                Scene(
                    narration=line,
                    image_prompt=line,
                    duration=4.0,
                )
            )

        return scenes