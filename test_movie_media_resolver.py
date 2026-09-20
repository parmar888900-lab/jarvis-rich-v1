import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory

from backend.services.storyboard.movie_visual_beat_planner import (
    MovieVisualBeat,
)
from backend.services.video.media_asset import MediaAsset
from backend.services.video.movie_media_resolver import (
    MovieMediaResolver,
)


class FakeLicensedProvider:

    async def search_and_download(
        self,
        *,
        query,
        content_id,
        limit=2,
    ):
        path = Path(
            "generated"
        ) / "resolver_test_asset.jpg"

        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        path.write_bytes(
            b"resolver-test"
        )

        return [
            MediaAsset(
                asset_id="fake-1",
                asset_type="image",
                file_path=str(path),
                source_url=(
                    "https://example.com/"
                    + query.replace(" ", "_")
                ),
                source_name="Fake Licensed Provider",
                creator="Test Creator",
                license_name="CC0",
                license_url=(
                    "https://creativecommons.org/publicdomain/zero/1.0/"
                ),
                attribution_required=False,
                commercial_use_allowed=True,
                relevance_score=90.0,
                width=1920,
                height=1080,
                content_id=content_id,
            )
        ]


async def main():

    beats = [
        MovieVisualBeat(
            beat_id="n1_b1",
            narration_index=1,
            purpose="hook_subject",
            visual_query=(
                "Doctor Strange Mirror Dimension"
            ),
            preferred_media=[
                "licensed_image"
            ],
            target_duration=2.2,
            priority="high",
            evidence_ids=[
                "E3",
            ],
        ),
        MovieVisualBeat(
            beat_id="n1_b2",
            narration_index=1,
            purpose="hook_detail",
            visual_query=(
                "Doctor Strange visual effects"
            ),
            preferred_media=[
                "licensed_image"
            ],
            target_duration=2.6,
            priority="high",
            evidence_ids=[
                "E3",
                "E4",
            ],
        ),
    ]

    resolver = MovieMediaResolver(
        providers=[
            FakeLicensedProvider(),
        ]
    )

    result = await resolver.resolve(
        beats=beats,
        content_id="movie-resolver-test-001",
        movie_title="Doctor Strange",
    )

    print()
    print(
        "========== MOVIE MEDIA RESOLUTION =========="
    )

    for item in result:

        print(
            item.beat_id,
            "|",
            item.status,
            "|",
            (
                item.asset.source_name
                if item.asset
                else "NONE"
            ),
            "|",
            (
                item.asset.license_name
                if item.asset
                else "NONE"
            ),
            "|",
            item.visual_query,
        )


asyncio.run(main())
