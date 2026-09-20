import asyncio

from backend.models.generated_content import GeneratedContent
from backend.services.storyboard.scene import Scene
from backend.services.image_generation.models import GeneratedImage
from backend.services.video.production_package import ProductionPackageBuilder


async def main():

    content = GeneratedContent(
        title="Piper Production Test",
        hashtags=[
            "#jarvis",
            "#test",
        ],
        script_lines=[
            "Jarvis is online.",
            "The production pipeline is ready for testing.",
        ],
        metadata={
            "test": True,
        },
    )

    scenes = [
        Scene(
            narration="Jarvis is online.",
            image_prompt="Futuristic artificial intelligence interface.",
            duration=4.0,
        ),
        Scene(
            narration="The production pipeline is ready for testing.",
            image_prompt="Futuristic video production system.",
            duration=4.0,
        ),
    ]

    image_path = (
        "generated/images/"
        "jarvis_4532eb39bbb042dab9fa02bf00229b0e.png"
    )

    images = [
        GeneratedImage(
            prompt=scenes[0].image_prompt,
            image_path=image_path,
            provider="flux-comfyui",
            width=720,
            height=1280,
        ),
        GeneratedImage(
            prompt=scenes[1].image_prompt,
            image_path=image_path,
            provider="flux-comfyui",
            width=720,
            height=1280,
        ),
    ]

    builder = ProductionPackageBuilder()

    result = await builder.build(
        content=content,
        scenes=scenes,
        images=images,
        trend={
            "source": "production_test",
        },
    )

    print("PACKAGE:", result["package_dir"])
    print("SCENES:", result["scene_count"])
    print("STORYBOARD DURATION:", result["duration"])
    print("VOICE STATUS:", result["voice"]["status"])
    print("VOICE PROVIDER:", result["voice"]["provider"])
    print("VOICE DURATION:", result["voice"]["duration"])
    print("VOICE PATH:", result["voice"]["audio_path"])


asyncio.run(main())
