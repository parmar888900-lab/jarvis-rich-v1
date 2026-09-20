from pathlib import Path
import asyncio

from backend.services.video.media_asset import MediaAsset
from backend.services.video.source_clip_indexer import SourceClipIndexer
from backend.services.video.clip_matcher import ClipMatcher
from backend.services.video.reference_profiles import get_profile
from backend.services.video_renderer.matched_clip_renderer import (
    MatchedClipRenderer,
)


def load_assets():

    root = Path(
        "generated/media/internet_archive"
    )

    assets = []

    for index, path in enumerate(
        sorted(
            root.glob(
                "source-footage-test-01*"
            )
        ),
        start=1,
    ):

        if path.suffix.lower() not in {
            ".mp4",
            ".webm",
            ".mov",
            ".m4v",
        }:
            continue

        assets.append(
            MediaAsset(
                asset_id=f"science-source-{index}",
                asset_type="video",
                file_path=str(path),
                source_url="local-test",
                source_name="Internet Archive",
                license_name="Inherited test license",
                commercial_use_allowed=True,
                relevance_score=80.0,
                content_id="science-preview",
            )
        )

    return assets


async def main():

    indexer = SourceClipIndexer()

    clips = indexer.index_assets(
        assets=load_assets(),
        content_id="science-render-preview",
    )

    matcher = ClipMatcher()

    beats = [
        {
            "beat_id": "s1",
            "query": "jet engine exterior",
        },
        {
            "beat_id": "s2",
            "query": "jet engine turbine blades",
        },
        {
            "beat_id": "s3",
            "query": "air entering jet engine",
        },
        {
            "beat_id": "s4",
            "query": "aircraft jet engine operating",
        },
    ]

    matches = matcher.match_many(
        beats=beats,
        clips=clips,
    )

    print(
        "MATCHES:",
        len(matches),
    )

    renderer = (
        MatchedClipRenderer()
    )

    result = await renderer.render(
        title="Jet Engine Matched Clip Test",
        matches=matches,
        profile=get_profile(
            "science_explainer"
        ),
    )

    print()
    print(
        "========== MATCHED RENDER =========="
    )

    for key, value in result.items():
        print(
            key,
            ":",
            value,
        )


asyncio.run(main())
