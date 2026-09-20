import asyncio
from pathlib import Path

from backend.services.video.media_asset import MediaAsset
from backend.services.video.source_clip_indexer import SourceClipIndexer
from backend.services.video.visual_beat_source_planner import (
    VisualBeatSourcePlanner,
)
from backend.services.video.strict_clip_matcher import (
    StrictClipMatcher,
)


def load_assets():

    root = Path(
        "generated/media/internet_archive"
    )

    output = []

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

        output.append(
            MediaAsset(
                asset_id=(
                    f"strict-source-{index}"
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
                content_id="strict-test",
            )
        )

    return output


async def main():

    planner = (
        VisualBeatSourcePlanner()
    )

    beats = await planner.plan(
        topic="how jet engines work",
        format_name=(
            "science_explainer"
        ),
        beat_count=8,
    )

    indexer = (
        SourceClipIndexer()
    )

    clips = indexer.index_assets(
        assets=load_assets(),
        content_id=(
            "strict-jet-engine-test"
        ),
    )

    matcher = (
        StrictClipMatcher()
    )

    matches = matcher.match_many(
        beats=beats,
        clips=clips,
    )

    print()
    print(
        "========== STRICT JET MATCHES =========="
    )

    print(
        "BEATS:",
        len(beats),
    )

    print(
        "CLIPS:",
        len(clips),
    )

    print(
        "MATCHED:",
        len(matches),
    )

    for match in matches:

        print()
        print(
            match.beat_id,
            "|",
            match.visual_goal,
        )

        print(
            "CLIP:",
            match.clip_id,
            "|",
            match.start_time,
            "->",
            match.end_time,
        )

        print(
            "POS:",
            match.positive_score,
            "| NEG:",
            match.negative_score,
            "| FINAL:",
            match.final_score,
        )

        print(
            "PREVIEW:",
            match.preview_path,
        )


asyncio.run(main())
