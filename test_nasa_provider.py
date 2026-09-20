import asyncio

from backend.services.video.media_sources.nasa import (
    NasaVideoProvider,
)


async def main():

    provider = NasaVideoProvider()

    queries = [
        "jet aircraft engine",
        "turbofan engine",
        "jet engine combustion",
        "gas turbine engine",
    ]

    for query in queries:

        print()
        print(
            "==========",
            query,
            "=========="
        )

        assets = await provider.search_and_download(
            query=query,
            content_id="nasa-jet-test",
            limit=2,
        )

        print(
            "ASSETS:",
            len(assets),
        )

        for asset in assets:

            print(
                asset.asset_id,
                "|",
                asset.file_path,
                "|",
                asset.source_name,
            )


asyncio.run(main())
