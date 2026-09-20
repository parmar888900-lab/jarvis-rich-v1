import asyncio
from pathlib import Path

from backend.services.video.media_asset import MediaAsset
from backend.services.video.source_clip_indexer import (
    SourceClipIndexer,
)
from backend.services.video.clip_matcher import ClipMatcher
from backend.services.video_renderer.luxury_benchmark_renderer import (
    LuxuryBenchmarkRenderer,
)


VIDEO_EXTENSIONS = {
    ".mp4",
    ".webm",
    ".mov",
    ".m4v",
}


def collect_assets():

    roots = [
        (
            Path(
                "generated/media/"
                "internet_archive"
            ),
            "Internet Archive",
        ),
        (
            Path(
                "generated/media/nasa"
            ),
            "NASA",
        ),
        (
            Path(
                "generated/licensed_media"
            ),
            "Licensed Media",
        ),
        (
            Path(
                "media_library/luxury"
            ),
            "Local Media Library",
        ),
    ]

    assets = []

    asset_number = 0

    for root, source_name in roots:

        if not root.exists():
            continue

        for path in root.rglob("*"):

            if (
                not path.is_file()
                or path.suffix.lower()
                not in VIDEO_EXTENSIONS
            ):
                continue

            asset_number += 1

            assets.append(
                MediaAsset(
                    asset_id=(
                        f"luxury-v2-source-"
                        f"{asset_number:03d}"
                    ),
                    asset_type="video",
                    file_path=str(path),
                    source_url=(
                        f"local:{path}"
                    ),
                    source_name=(
                        source_name
                    ),
                    license_name=(
                        "Existing local asset"
                    ),
                    commercial_use_allowed=True,
                    relevance_score=70.0,
                    content_id=(
                        "luxury-benchmark-v2"
                    ),
                )
            )

    return assets


async def main():

    assets = collect_assets()

    print(
        "SOURCE VIDEOS:",
        len(assets),
    )

    if not assets:
        raise RuntimeError(
            "No local luxury video sources found."
        )

    ########################################################
    # Index all sources.
    ########################################################

    indexer = SourceClipIndexer()

    clips = indexer.index_assets(
        assets=assets,
        content_id="luxury-benchmark-v2",
    )

    print(
        "CANDIDATE CLIPS:",
        len(clips),
    )

    if len(clips) < 30:
        raise RuntimeError(
            "Need at least 30 candidate clips."
        )

    ########################################################
    # Rank clips for Rolex/product visual quality.
    ########################################################

    matcher = ClipMatcher()

    beats = []

    visual_queries = [
        "Rolex Daytona watch macro close up",
        "Rolex Daytona dial detail",
        "luxury watch chronograph pushers",
        "Rolex Daytona bracelet detail",
        "Rolex Daytona wrist shot",
        "mechanical watch movement",
        "luxury watch case close up",
        "Rolex Daytona crown detail",
        "premium wristwatch cinematic shot",
        "Rolex Daytona chronograph dial",
    ]

    for index in range(30):

        query = visual_queries[
            index % len(
                visual_queries
            )
        ]

        beats.append(
            {
                "beat_id": (
                    f"luxury_{index + 1:02d}"
                ),
                "query": query,
            }
        )

    matches = matcher.match_many(
        beats=beats,
        clips=clips,
        max_reuse_per_source=10,
    )

    print(
        "SEMANTIC MATCHES:",
        len(matches),
    )

    ########################################################
    # Convert ranked matches back into indexed clips.
    ########################################################

    by_clip_id = {
        clip.clip_id: clip
        for clip in clips
    }

    selected = []

    used = set()

    for match in matches:

        clip = by_clip_id.get(
            match.clip_id
        )

        if clip is None:
            continue

        if clip.clip_id in used:
            continue

        used.add(
            clip.clip_id
        )

        selected.append(
            clip
        )

    ########################################################
    # Fill remaining slots with diverse clips only if needed.
    ########################################################

    if len(selected) < 30:

        for clip in clips:

            if clip.clip_id in used:
                continue

            selected.append(
                clip
            )

            used.add(
                clip.clip_id
            )

            if len(selected) >= 30:
                break

    if len(selected) < 30:
        raise RuntimeError(
            "Could not produce 30 luxury shots."
        )

    renderer = LuxuryBenchmarkRenderer()

    result = await renderer.render(
        title=(
            "Rolex Daytona "
            "Luxury Reference Benchmark V2"
        ),
        indexed_clips=selected,
    )

    print()
    print(
        "========== LUXURY BENCHMARK V2 =========="
    )

    for key, value in result.items():

        print(
            key,
            ":",
            value,
        )


if __name__ == "__main__":
    asyncio.run(main())
