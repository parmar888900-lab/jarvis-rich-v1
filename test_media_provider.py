import asyncio

from backend.services.video.media_sources.wikimedia import (
    WikimediaCommonsProvider,
)
from backend.services.video.asset_collector import (
    AssetCollector,
)


async def main():
    provider = WikimediaCommonsProvider()

    assets = await provider.search_and_download(
        query="airplane rounded windows aircraft",
        content_id="media-test-001",
        limit=3,
    )

    print("FOUND:", len(assets))

    collector = AssetCollector()

    authorized = collector.authorize(
        assets,
        content_id="media-test-001",
    )

    print("AUTHORIZED:", len(authorized))

    for asset in authorized:
        print()
        print("TYPE:", asset.asset_type)
        print("FILE:", asset.file_path)
        print("SOURCE:", asset.source_name)
        print("LICENSE:", asset.license_name)
        print("RELEVANCE:", asset.relevance_score)
        print("URL:", asset.source_url)


asyncio.run(main())
