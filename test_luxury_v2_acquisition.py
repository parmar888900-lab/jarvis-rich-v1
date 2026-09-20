import asyncio
from pathlib import Path

from backend.services.video.source_footage_resolver import (
    SourceFootageResolver,
)


async def main():

    print(
        "========== LUXURY V2 ACQUISITION =========="
    )

    resolver = SourceFootageResolver()

    topics = [
        "Rolex Daytona",
        "Rolex Cosmograph Daytona",
        "luxury chronograph watch",
        "mechanical luxury watch",
        "Swiss luxury watch movement",
        "luxury wristwatch macro",
    ]

    all_assets = {}
    results = []

    for number, topic in enumerate(
        topics,
        start=1,
    ):

        print()
        print(
            f"[{number}/{len(topics)}] SEARCH:",
            topic,
        )

        result = await resolver.resolve(
            format_name="luxury_product",
            topic=topic,
            content_id=(
                f"luxury-v2-acquisition-{number:02d}"
            ),
            minimum_assets=2,
            target_assets=6,
        )

        results.append(
            result
        )

        print(
            "STATUS:",
            result.status,
        )

        print(
            "FOUND:",
            len(result.assets),
        )

        for asset in result.assets:

            key = (
                asset.source_url
                or asset.file_path
            )

            if key not in all_assets:
                all_assets[key] = asset

            print(
                " ",
                asset.source_name,
                "|",
                asset.license_name,
                "|",
                asset.file_path,
            )

    print()
    print(
        "========== ACQUISITION SUMMARY =========="
    )

    print(
        "UNIQUE ASSETS:",
        len(all_assets),
    )

    source_counts = {}

    for asset in all_assets.values():

        source_counts[
            asset.source_name
        ] = (
            source_counts.get(
                asset.source_name,
                0,
            )
            + 1
        )

    for source, count in sorted(
        source_counts.items()
    ):

        print(
            source,
            ":",
            count,
        )

    print()
    print(
        "========== ACQUIRED FILES =========="
    )

    for number, asset in enumerate(
        all_assets.values(),
        start=1,
    ):

        path = Path(
            asset.file_path
        )

        print()
        print(
            number,
            "|",
            asset.source_name,
        )

        print(
            "LICENSE:",
            asset.license_name,
        )

        print(
            "COMMERCIAL:",
            asset.commercial_use_allowed,
        )

        print(
            "EXISTS:",
            path.exists(),
        )

        print(
            "FILE:",
            path,
        )


if __name__ == "__main__":
    asyncio.run(main())
