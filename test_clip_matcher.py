from pathlib import Path

from backend.services.video.media_asset import (
    MediaAsset,
)
from backend.services.video.source_clip_indexer import (
    SourceClipIndexer,
)
from backend.services.video.clip_matcher import (
    ClipMatcher,
)


def load_assets(
    prefix: str,
):

    root = Path(
        "generated/media/"
        "internet_archive"
    )

    assets = []

    for index, path in enumerate(
        sorted(
            root.glob(
                f"{prefix}*"
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
                asset_id=(
                    f"matcher-source-{index}"
                ),
                asset_type="video",
                file_path=str(path),
                source_url="local-test",
                source_name=(
                    "Internet Archive"
                ),
                license_name=(
                    "Inherited test license"
                ),
                commercial_use_allowed=True,
                relevance_score=80.0,
                content_id=prefix,
            )
        )

    return assets


indexer = SourceClipIndexer()

matcher = ClipMatcher()


############################################################
# SCIENCE TEST
############################################################

science_assets = load_assets(
    "source-footage-test-01"
)

science_clips = indexer.index_assets(
    assets=science_assets,
    content_id="matcher-science",
)

science_beats = [
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

science_matches = matcher.match_many(
    beats=science_beats,
    clips=science_clips,
)


print()
print(
    "========== SCIENCE MATCHES =========="
)

for match in science_matches:

    print(
        match.beat_id,
        "|",
        match.query,
        "|",
        match.clip_id,
        "|",
        match.start_time,
        "->",
        match.end_time,
        "| score:",
        match.semantic_score,
    )


############################################################
# LUXURY TEST
############################################################

luxury_assets = load_assets(
    "source-footage-test-02"
)

luxury_clips = indexer.index_assets(
    assets=luxury_assets,
    content_id="matcher-luxury",
)

luxury_beats = [
    {
        "beat_id": "w1",
        "query": "Rolex Daytona watch face",
    },
    {
        "beat_id": "w2",
        "query": "luxury watch chronograph dial",
    },
    {
        "beat_id": "w3",
        "query": "mechanical watch movement close up",
    },
    {
        "beat_id": "w4",
        "query": "Rolex watch bracelet detail",
    },
]

luxury_matches = matcher.match_many(
    beats=luxury_beats,
    clips=luxury_clips,
    max_reuse_per_source=20,
)


print()
print(
    "========== LUXURY MATCHES =========="
)

for match in luxury_matches:

    print(
        match.beat_id,
        "|",
        match.query,
        "|",
        match.clip_id,
        "|",
        match.start_time,
        "->",
        match.end_time,
        "| score:",
        match.semantic_score,
    )
