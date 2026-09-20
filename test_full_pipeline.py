import asyncio

from backend.services.pipelines.video_pipeline import VideoPipeline


async def main():

    pipeline = VideoPipeline()

    trend = {
        "title": "Why AI-generated videos are becoming more realistic",
        "research": (
            "AI video systems are improving rapidly in image quality, "
            "motion consistency, voice generation, and automated editing. "
            "Creators increasingly use AI tools to generate scripts, "
            "visuals, narration, captions, and final videos."
        ),
    }

    result = await pipeline.run(
        trend
    )

    print()
    print("PIPELINE STATUS:")
    print(result["status"])

    print()
    print("VIDEO:")
    print(result["video"])

    print()
    print("CONTENT TITLE:")
    print(result["generated"].title)

    print()
    print("SCENES:")
    for index, scene in enumerate(
        result["storyboard"],
        start=1,
    ):
        print(
            f"{index}. "
            f"{scene.start_time:.3f} -> "
            f"{scene.end_time:.3f} | "
            f"{scene.narration}"
        )

    print()
    print("IMAGES:")
    for image in result["images"]:
        print(image.image_path)

    print()
    print("AUDIO:")
    print(
        result[
            "production_package"
        ]["voice"]["audio_path"]
    )


asyncio.run(main())
