import asyncio

from backend.models.generated_content import GeneratedContent
from backend.services.storyboard.scene import Scene
from backend.services.image_generation.models import GeneratedImage
from backend.services.video_renderer.renderer import VideoRenderer


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
            duration=1.277,
            start_time=0.0,
            end_time=1.277,
        ),
        Scene(
            narration="The production pipeline is ready for testing.",
            image_prompt="Futuristic video production system.",
            duration=2.183,
            start_time=1.277,
            end_time=3.460,
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

    production_package = {
        "voice": {
            "audio_path": (
                "generated/packages/"
                "Piper_Production_Test/"
                "Piper_Production_Test.wav"
            ),
        },
        "duration": 3.460,
    }

    renderer = VideoRenderer()

    result = await renderer.render(
        content=content,
        scenes=scenes,
        images=images,
        production_package=production_package,
    )

    print(result)


asyncio.run(main())

