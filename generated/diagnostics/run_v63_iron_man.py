import asyncio
import json
import time
import traceback
from pathlib import Path

from backend.services.pipelines.video_pipeline import VideoPipeline

ROOT = Path(r"C:\Users\hp\jarvis.ai")
OUT = ROOT / "generated" / "diagnostics" / "v63_iron_man_result.json"
OUT.parent.mkdir(parents=True, exist_ok=True)

TOPIC = "Why Iron Man's first suit-building scene became iconic"

trend = {
    "content_id": "v63_iron_man_first_render",
    "title": TOPIC,
    "topic": TOPIC,
    "genre": "famous_movie_commentary",
    "content_format": "famous_movie_commentary",
    "locked_format": "famous_movie_commentary",
    "content_strategy": "evergreen_storytelling",
    "requires_trend": False,
}

async def main():
    print("=" * 72)
    print(" RICH V1 - V6.3 FIRST MARVEL PRODUCTION RUN")
    print("=" * 72)
    print()
    print("MOVIE: Iron Man")
    print("TOPIC:", TOPIC)
    print()
    print("Starting production pipeline...")
    print()

    started = time.time()

    try:
        pipeline = VideoPipeline()

        result = await pipeline.run(trend)

        elapsed = time.time() - started

        payload = {
            "status": "PASS",
            "elapsed_seconds": round(elapsed, 2),
            "topic": TOPIC,
            "result": result,
        }

        OUT.write_text(
            json.dumps(
                payload,
                indent=2,
                default=str,
            ),
            encoding="utf-8",
        )

        print()
        print("=" * 72)
        print(" V6.3 IRON MAN PRODUCTION COMPLETE")
        print("=" * 72)
        print("elapsed_seconds:", round(elapsed, 2))

        if isinstance(result, dict):

            video_path = (
                result.get("video_path")
                or result.get("output_path")
                or result.get("final_video")
                or result.get("render_path")
            )

            print("video_path:", video_path)

            movie_media = result.get(
                "v6_movie_media",
                {},
            )

            print()
            print("MOVIE MEDIA")
            print(
                "status:",
                movie_media.get("status"),
            )
            print(
                "movie_title:",
                movie_media.get("movie_title"),
            )
            print(
                "resolved_beats:",
                movie_media.get("resolved_beats"),
            )
            print(
                "video_assets:",
                movie_media.get("video_assets"),
            )
            print(
                "image_assets:",
                movie_media.get("image_assets"),
            )
            print(
                "unresolved_beats:",
                movie_media.get("unresolved_beats"),
            )

            matching = result.get(
                "v6_video_matching",
                {},
            )

            print()
            print("VIDEO MATCHING")
            print(
                "status:",
                matching.get("status"),
            )
            print(
                "reason:",
                matching.get("reason"),
            )
            print(
                "authorized_video_assets:",
                matching.get(
                    "authorized_video_assets"
                ),
            )
            print(
                "indexed_clips:",
                matching.get("indexed_clips"),
            )
            print(
                "matched_beats:",
                matching.get("matched_beats"),
            )

        print()
        print("FULL RESULT:")
        print(OUT)
        print()
        print("V6.3 IRON MAN: PASS")

    except Exception as exc:

        elapsed = time.time() - started

        payload = {
            "status": "FAIL",
            "elapsed_seconds": round(elapsed, 2),
            "topic": TOPIC,
            "exception_type": type(exc).__name__,
            "exception": str(exc),
            "traceback": traceback.format_exc(),
        }

        OUT.write_text(
            json.dumps(
                payload,
                indent=2,
            ),
            encoding="utf-8",
        )

        print()
        print("=" * 72)
        print(" V6.3 IRON MAN: FAIL")
        print("=" * 72)
        print(
            type(exc).__name__ + ":",
            str(exc),
        )
        print()
        traceback.print_exc()
        print()
        print("FAILURE REPORT:")
        print(OUT)

        raise

asyncio.run(main())
