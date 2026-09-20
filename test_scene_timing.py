import asyncio

from backend.services.storyboard.scene import Scene
from backend.services.video.voice_generator import VoiceGenerator


async def main():

    scenes = [
        Scene(
            narration="Jarvis is online.",
            image_prompt="Jarvis interface",
        ),
        Scene(
            narration=(
                "The artificial intelligence system is now analyzing "
                "multiple sources of information and preparing the "
                "next stage of the content production pipeline."
            ),
            image_prompt="Artificial intelligence system",
        ),
    ]

    voice = VoiceGenerator()

    result = await voice.generate_scenes(
        scenes,
        filename="scene_timing_test",
    )

    print("\nVOICE RESULT")
    print("STATUS:", result["status"])
    print("PROVIDER:", result["provider"])
    print("TOTAL DURATION:", result["duration"])
    print("AUDIO:", result["audio_path"])

    print("\nSCENE TIMINGS")

    for index, scene in enumerate(
        scenes,
        start=1,
    ):
        print(
            f"Scene {index}: "
            f"start={scene.start_time:.3f}, "
            f"end={scene.end_time:.3f}, "
            f"duration={scene.duration:.3f}"
        )

    print("\nTIMING CHECKS")

    print(
        "SCENE 2 LONGER:",
        scenes[1].duration > scenes[0].duration,
    )

    print(
        "SCENE 2 STARTS AFTER SCENE 1:",
        abs(
            scenes[1].start_time
            - scenes[0].end_time
        ) < 0.01,
    )

    print(
        "FINAL END MATCHES AUDIO:",
        abs(
            scenes[-1].end_time
            - result["duration"]
        ) < 0.05,
    )


asyncio.run(main())
