import asyncio

from backend.services.video.media_sources.wikimedia import (
    WikimediaCommonsProvider,
)
from backend.services.video.asset_collector import (
    AssetCollector,
)
from backend.services.video_renderer.movie_clip_renderer import (
    MovieClipRenderer,
)


async def main():

    content_id = "legal-movie-test-002"

    provider = WikimediaCommonsProvider()

    print(
        "Downloading verified public-domain movie..."
    )

    movie = await provider.download_exact_file(
        file_title=(
            'File:The Great Train Robbery '
            '(1903) - yt.webm'
        ),
        content_id=content_id,
    )

    if movie is None:
        raise RuntimeError(
            "Exact public-domain movie download failed."
        )

    print("TYPE:", movie.asset_type)
    print("SOURCE:", movie.source_url)
    print("LICENSE:", movie.license_name)
    print("FILE:", movie.file_path)

    if movie.asset_type != "video":
        raise RuntimeError(
            "Downloaded Commons file is not video."
        )

    collector = AssetCollector()

    authorized = collector.authorize(
        [movie],
        content_id=content_id,
    )

    renderer = MovieClipRenderer()

    result = await renderer.render(
        asset=authorized[0],
        title="The Great Train Robbery",
        hook_text=(
            "One of cinema's earliest "
            "action films"
        ),
    )

    print()
    print("========== MOVIE SHORT ==========")
    print("STATUS:", result["status"])
    print("VIDEO:", result["video_path"])
    print("DURATION:", result["duration"])
    print("LICENSE:", result["license_name"])


asyncio.run(main())
