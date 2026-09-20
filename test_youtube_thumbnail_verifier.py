from backend.services.research.providers.youtube import (
    YouTubeDiscoveryProvider,
)
from backend.services.research.youtube_thumbnail_verifier import (
    YouTubeThumbnailVerifier,
)


provider = YouTubeDiscoveryProvider()
verifier = YouTubeThumbnailVerifier()

queries = [
    "Rolex Daytona official",
    "Rolex Daytona close up",
    "Rolex Daytona movement",
]

positive = [
    "Rolex Daytona watch close up",
    "luxury wristwatch product shot",
    "watch dial macro photography",
    "mechanical watch movement",
    "Rolex chronograph detail",
]

negative = [
    "person talking to camera",
    "podcast interview",
    "presenter sitting at desk",
    "face portrait",
    "text-heavy thumbnail",
    "generic talking-head review",
]

for query in queries:

    print()
    print(
        "==========",
        query,
        "=========="
    )

    candidates = provider.search(
        query=query,
        limit=6,
    )

    for candidate in candidates:

        result = verifier.verify(
            thumbnail_url=(
                candidate.thumbnail_url
            ),
            positive_prompts=positive,
            negative_prompts=negative,
        )

        print()
        print(
            candidate.channel_title,
            "|",
            candidate.title,
        )

        print(
            "AUTH:",
            candidate.authority_score,
            "| DISCOVERY:",
            candidate.final_score,
        )

        print(
            "THUMB:",
            result.valid,
            "| POS:",
            result.positive_score,
            "| NEG:",
            result.negative_score,
            "| MARGIN:",
            result.margin,
            "|",
            result.reason,
        )
