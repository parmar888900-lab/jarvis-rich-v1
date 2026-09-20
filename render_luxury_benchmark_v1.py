import asyncio
from pathlib import Path

from backend.services.video.media_asset import (
    MediaAsset,
)
from backend.services.video.source_clip_indexer import (
    SourceClipIndexer,
)
from backend.services.video_renderer.luxury_benchmark_renderer import (
    LuxuryBenchmarkRenderer,
)


async def main():

    root = Path(
        "generated/media/internet_archive"
    )

    files = sorted(
        root.glob(
            "source-footage-test-02*"
        )
    )

    video_files = [
        path
        for path in files
        if path.suffix.lower()
        in {
            ".mp4",
            ".webm",
            ".mov",
            ".m4v",
        }
    ]

    if not video_files:
        raise RuntimeError(
            "Real Rolex source footage not found."
        )

    source = video_files[0]

    print(
        "REAL SOURCE:",
        source,
    )

    asset = MediaAsset(
        asset_id="luxury-rolex-source",
        asset_type="video",
        file_path=str(source),
        source_url="local-existing-source",
        source_name="Internet Archive",
        license_name="Inherited source license",
        commercial_use_allowed=True,
        relevance_score=80.0,
        content_id="luxury-benchmark-v1",
    )

    indexer = SourceClipIndexer()

    indexed = indexer.index_asset(
        asset=asset,
        content_id="luxury-benchmark-v1",
    )

    print(
        "INDEXED:",
        len(indexed),
    )

    if len(indexed) < 30:
        raise RuntimeError(
            "Need at least 30 indexed luxury clips."
        )

    renderer = (
        LuxuryBenchmarkRenderer()
    )

    result = await renderer.render(
        title=(
            "Rolex Daytona "
            "Luxury Reference Benchmark"
        ),
        indexed_clips=indexed,
    )

    print()
    print(
        "========== LUXURY BENCHMARK =========="
    )

    for key, value in result.items():

        print(
            key,
            ":",
            value,
        )


asyncio.run(main())
