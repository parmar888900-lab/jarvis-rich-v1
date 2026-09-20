from pathlib import Path

from backend.services.video.media_asset import (
    MediaAsset,
)
from backend.services.video.source_clip_indexer import (
    SourceClipIndexer,
)


def assets_from_folder(
    folder: Path,
    content_prefix: str,
):

    output = []

    for index, path in enumerate(
        sorted(
            folder.glob(
                f"{content_prefix}*"
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

        output.append(
            MediaAsset(
                asset_id=(
                    f"test-source-{index}"
                ),
                asset_type="video",
                file_path=str(path),
                source_url="local-test",
                source_name=(
                    "Internet Archive"
                ),
                license_name=(
                    "Test inherited license"
                ),
                commercial_use_allowed=True,
                relevance_score=80.0,
                content_id=content_prefix,
            )
        )

    return output


root = Path(
    "generated/media/"
    "internet_archive"
)

science = assets_from_folder(
    root,
    "source-footage-test-01",
)

luxury = assets_from_folder(
    root,
    "source-footage-test-02",
)

indexer = SourceClipIndexer()


for name, assets in (
    (
        "SCIENCE",
        science,
    ),
    (
        "LUXURY",
        luxury,
    ),
):

    clips = indexer.index_assets(
        assets=assets,
        content_id=(
            f"clip-index-{name.lower()}"
        ),
    )

    print()
    print(
        "==========",
        name,
        "CLIP INDEX =========="
    )

    print(
        "SOURCE VIDEOS:",
        len(assets),
    )

    print(
        "INDEXED CLIPS:",
        len(clips),
    )

    for clip in clips[:15]:

        print(
            clip.clip_id,
            "|",
            clip.start_time,
            "->",
            clip.end_time,
            "|",
            clip.duration,
            "|",
            clip.preview_path,
        )
