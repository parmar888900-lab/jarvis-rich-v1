from backend.services.video.source_footage_resolver import SourceFootageResolver
from backend.services.video.media_asset import MediaAsset
from backend.services.video.media_sources.nasa import NasaVideoProvider


def test_science_topic_title_is_normalized_for_archive_search():
    queries = SourceFootageResolver._queries(
        format_name="science_explainer",
        topic=(
            "Why the James Webb Telescope's Gold Mirror "
            "Must Unfold in Space"
        ),
    )

    assert queries[0] == (
        "James Webb Space Telescope mirror unfolding"
    )
    assert "James Webb Space Telescope mirror alignment" in queries
    assert "Webb secondary mirror deploy" in queries
    assert "James Webb Space Telescope launch deployment" in queries
    assert len(queries) == len(set(query.lower() for query in queries))


def test_science_hook_strips_leading_nasa_possessive_for_catalogue_search():
    queries = SourceFootageResolver._queries(
        format_name="science_explainer",
        topic="Why NASA's James Webb Space Telescope unfolds in space",
    )

    assert queries[0] == "James Webb Space Telescope unfolding"


def test_non_science_topic_queries_are_preserved():
    queries = SourceFootageResolver._queries(
        format_name="business_wealth",
        topic="How Costco Makes Money",
    )

    assert queries[0] == "How Costco Makes Money"


def test_science_resolver_limits_nasa_to_one_asset_per_query():
    class RecordingNasa(NasaVideoProvider):
        limits = []

        async def search_and_download(self, *, query, content_id, limit):
            self.limits.append(limit)
            return [
                MediaAsset(
                    asset_id=f"nasa-{len(self.limits)}",
                    asset_type="video",
                    file_path=__file__,
                    source_url=f"https://images.nasa.gov/{len(self.limits)}",
                    source_name="NASA Images",
                    commercial_use_allowed=True,
                    content_id=content_id,
                )
            ]

    class AcceptAll:
        @staticmethod
        def validate_asset(asset, *, content_id):
            return True, ""

    provider = RecordingNasa()
    resolver = SourceFootageResolver(
        primary_providers=[],
        fallback_providers=[],
        asset_collector=AcceptAll(),
    )
    resolver.science_providers = [provider]

    import asyncio

    asyncio.run(resolver.resolve(
        format_name="science_explainer",
        topic="Why the James Webb Telescope must unfold in space",
        content_id="test",
        minimum_assets=1,
        target_assets=2,
    ))

    assert provider.limits == [1, 1]
