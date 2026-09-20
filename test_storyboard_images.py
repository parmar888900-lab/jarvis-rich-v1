import asyncio

from backend.models.generated_content import GeneratedContent
from backend.services.storyboard.generator import StoryboardGenerator
from backend.services.image_generation.generator import ImageGenerator


async def main():
    content = GeneratedContent(
        title="Future Cars",
        script_lines=[
            "A futuristic silver sports car speeds through a neon-lit city at night.",
            "The car races past towering holographic billboards as rain reflects the neon lights.",
        ],
    )

    scenes = StoryboardGenerator().generate(content)
    generator = ImageGenerator()
    images = []

    print("SCENE COUNT:", len(scenes))

    for index, scene in enumerate(scenes, start=1):
        print(f"GENERATING {index}/{len(scenes)}")

        image = await generator.generate(scene)
        images.append(image)

        print(f"DONE {index}: {image.image_path}")

    print("IMAGE COUNT:", len(images))
    print("SUCCESS:", len(images) == len(scenes))


asyncio.run(main())
