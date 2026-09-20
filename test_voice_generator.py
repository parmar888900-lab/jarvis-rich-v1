import asyncio

from backend.services.video.voice_generator import VoiceGenerator


async def main():
    generator = VoiceGenerator()

    result = await generator.generate(
        script=(
            "Jarvis is online. "
            "The content pipeline is ready for production."
        ),
        filename="voice_generator_test",
    )

    print(result)


asyncio.run(main())
