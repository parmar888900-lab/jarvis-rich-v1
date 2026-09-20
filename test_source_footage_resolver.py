import asyncio

from backend.services.video.source_footage_resolver import (
    SourceFootageResolver,
)


async def main():

    resolver = (
        SourceFootageResolver()
    )

    cases = [
        (
            "science_explainer",
            "how jet engines work",
        ),
        (
            "luxury_product",
            "Rolex Daytona",
        ),
    ]

    for index, (
        format_name,
        topic,
    ) in enumerate(
        cases,
        start=1,
    ):

        result = await resolver.resolve(
            format_name=format_name,
            topic=topic,
            content_id=(
                f"source-footage-test-"
                f"{index:02d}"
            ),
            minimum_assets=2,
            target_assets=4,
        )

        print()
        print(
            "========== SOURCE FOOTAGE =========="
        )

        print(
            "FORMAT:",
            format_name,
        )

        print(
            "TOPIC:",
            topic,
        )

        print(
            "STATUS:",
            result.status,
        )

        print(
            "PRIMARY:",
            len(
                result.primary_assets
            ),
        )

        print(
            "FALLBACK:",
            len(
                result.fallback_assets
            ),
        )

        print(
            "TOTAL:",
            len(
                result.assets
            ),
        )

        for asset in result.assets:

            print(
                asset.source_name,
                "|",
                asset.asset_type,
                "|",
                asset.license_name,
                "|",
                asset.file_path,
            )


asyncio.run(main())
