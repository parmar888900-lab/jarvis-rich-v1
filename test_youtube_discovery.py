from backend.services.research.providers.youtube import (
    YouTubeDiscoveryProvider,
)


provider = YouTubeDiscoveryProvider()

queries = [
    "Rolex Daytona official",
    "Rolex Daytona close up",
    "Rolex Daytona chronograph",
    "Rolex Daytona movement",
]

for query in queries:

    print()
    print(
        "==========",
        query,
        "=========="
    )

    results = provider.search(
        query=query,
        limit=5,
    )

    for item in results:

        print(
            round(
                item.final_score,
                2,
            ),
            "| authority:",
            item.authority_score,
            "|",
            item.channel_title,
            "|",
            item.title,
        )

        print(
            " ",
            item.watch_url,
        )
