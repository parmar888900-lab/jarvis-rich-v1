import asyncio

from backend.services.video.media_sources.wikimedia import (
    WikimediaCommonsProvider,
)


async def main():
    provider = WikimediaCommonsProvider()

    queries = [
        "railway wheelset",
        "train wheel rail",
        "railway wheel flange",
        "railroad wheel profile",
        "train bogie wheels",
    ]

    for query in queries:
        assets = await provider.search_and_download(
            query=query,
            content_id="rail-media-test",
            limit=3,
        )

        print()
        print("QUERY:", query)
        print("FOUND:", len(assets))

        for asset in assets:
            print(
                asset.asset_type,
                "|",
                asset.license_name,
                "|",
                asset.relevance_score,
                "|",
                asset.source_url,
            )


asyncio.run(main())
