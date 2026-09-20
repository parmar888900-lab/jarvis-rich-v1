import asyncio
import os

from backend.services.video.media_sources.pexels import (
    PexelsProvider,
)


async def main():

    if not os.environ.get(
        "PEXELS_API_KEY"
    ):
        raise RuntimeError(
            "PEXELS_API_KEY missing."
        )

    provider = PexelsProvider()

    assets = await provider.search_and_download(
        query="surreal city architecture",
        content_id="pexels-smoke-test",
        limit=2,
    )

    print()
    print("========== PEXELS SMOKE TEST ==========")
    print("ASSETS:", len(assets))

    for asset in assets:

        print(
            asset.asset_id,
            "|",
            asset.asset_type,
            "|",
            asset.license_name,
            "| relevance:",
            asset.relevance_score,
            "|",
            asset.width,
            "x",
            asset.height,
        )


asyncio.run(main())
