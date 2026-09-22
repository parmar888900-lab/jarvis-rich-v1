"""Topic-specific source-footage resolution for Jarvis Rich V1."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from backend.services.video.asset_collector import (
    AssetCollector,
)
from backend.services.video.media_asset import (
    MediaAsset,
)
from backend.services.video.media_sources.internet_archive import (
    InternetArchiveProvider,
)
from backend.services.video.media_sources.pexels import (
    PexelsProvider,
)
from backend.services.video.media_sources.wikimedia import (
    WikimediaCommonsProvider,
)
from backend.services.video.media_sources.nasa import NasaVideoProvider


@dataclass(slots=True)
class SourceFootageResult:
    format_name: str
    topic: str
    assets: list[MediaAsset] = field(
        default_factory=list
    )
    primary_assets: list[MediaAsset] = field(
        default_factory=list
    )
    fallback_assets: list[MediaAsset] = field(
        default_factory=list
    )
    attempted_queries: list[str] = field(
        default_factory=list
    )
    status: str = "unresolved"


class SourceFootageResolver:
    """
    Resolve real/topic-specific reusable footage before generic B-roll.

    Priority:
        1. Wikimedia Commons
        2. Internet Archive
        3. Pexels contextual fallback

    Unauthorized scraping/downloading is deliberately outside this
    resolver.
    """

    PRIMARY_LIMIT_PER_QUERY = 2
    FALLBACK_LIMIT_PER_QUERY = 2

    def __init__(
        self,
        *,
        primary_providers=None,
        fallback_providers=None,
        asset_collector=None,
    ) -> None:

        self.primary_providers = (
            primary_providers
            if primary_providers is not None
            else [
                WikimediaCommonsProvider(),
                InternetArchiveProvider(),
            ]
        )

        if fallback_providers is not None:

            self.fallback_providers = (
                fallback_providers
            )

        else:

            self.fallback_providers = []

            try:

                self.fallback_providers.append(
                    PexelsProvider()
                )

            except RuntimeError as exc:

                print(
                    "Pexels fallback unavailable: "
                    f"{exc}"
                )

        self.asset_collector = (
            asset_collector
            if asset_collector is not None
            else AssetCollector()
        )

        self.science_providers = [NasaVideoProvider()]

    async def resolve(
        self,
        *,
        format_name: str,
        topic: str,
        content_id: str,
        minimum_assets: int = 6,
        target_assets: int = 12,
    ) -> SourceFootageResult:

        queries = self._queries(
            format_name=format_name,
            topic=topic,
        )

        primary: list[
            MediaAsset
        ] = []

        fallback: list[
            MediaAsset
        ] = []

        used_urls: set[str] = set()

        ####################################################
        # Primary topic-specific footage
        ####################################################

        primary_providers = list(self.primary_providers)
        if str(format_name).strip().lower() in {
            "science_explainer", "science_engineering", "space_aviation",
        }:
            primary_providers = list(self.science_providers) + primary_providers

        for query in queries:

            if len(primary) >= target_assets:
                break

            for provider in primary_providers:

                try:

                    found = await provider.search_and_download(
                        query=query,
                        content_id=content_id,
                        limit=(
                            self.PRIMARY_LIMIT_PER_QUERY
                        ),
                    )

                except Exception:
                    continue

                for asset in found:

                    if (
                        asset.source_url
                        in used_urls
                    ):
                        continue

                    valid, _ = (
                        self.asset_collector
                        .validate_asset(
                            asset,
                            content_id=content_id,
                        )
                    )

                    if not valid:
                        continue

                    if asset.asset_type != "video":
                        continue

                    used_urls.add(
                        asset.source_url
                    )

                    primary.append(
                        asset
                    )

        ####################################################
        # Contextual fallback only when primary supply is
        # insufficient.
        ####################################################

        if len(primary) < minimum_assets:

            for query in queries:

                if (
                    len(primary)
                    + len(fallback)
                    >= target_assets
                ):
                    break

                for provider in self.fallback_providers:

                    try:

                        found = await provider.search_and_download(
                            query=query,
                            content_id=content_id,
                            limit=(
                                self.FALLBACK_LIMIT_PER_QUERY
                            ),
                        )

                    except Exception:
                        continue

                    for asset in found:

                        if (
                            asset.source_url
                            in used_urls
                        ):
                            continue

                        valid, _ = (
                            self.asset_collector
                            .validate_asset(
                                asset,
                                content_id=content_id,
                            )
                        )

                        if not valid:
                            continue

                        if asset.asset_type != "video":
                            continue

                        used_urls.add(
                            asset.source_url
                        )

                        fallback.append(
                            asset
                        )

        assets = (
            primary
            + fallback
        )[:target_assets]

        if len(assets) >= minimum_assets:
            status = "resolved"

        elif assets:
            status = "partial"

        else:
            status = (
                "insufficient_source_footage"
            )

        return SourceFootageResult(
            format_name=format_name,
            topic=topic,
            assets=assets,
            primary_assets=primary,
            fallback_assets=fallback,
            attempted_queries=queries,
            status=status,
        )

    @staticmethod
    def _queries(
        *,
        format_name: str,
        topic: str,
    ) -> list[str]:

        clean = " ".join(
            str(topic).split()
        ).strip()

        science_subject = clean

        if format_name == "science_explainer":
            science_subject = re.sub(
                r"^(?:why|how|what)\s+(?:the\s+)?",
                "",
                clean,
                flags=re.IGNORECASE,
            )
            science_subject = re.sub(
                r"\bmust\s+unfold\b",
                "unfolding",
                science_subject,
                flags=re.IGNORECASE,
            )
            science_subject = re.sub(
                r"\bJames\s+Webb\s+Telescope(?:['’]s)?\b",
                "James Webb Space Telescope",
                science_subject,
                flags=re.IGNORECASE,
            )
            science_subject = re.sub(
                r"\bgold\s+mirror\b",
                "mirror",
                science_subject,
                flags=re.IGNORECASE,
            )
            science_subject = re.sub(
                r"\s+in\s+space\s*$",
                "",
                science_subject,
                flags=re.IGNORECASE,
            )
            science_subject = " ".join(
                science_subject.split()
            ).strip()

        format_queries = {

            "movie_facts": [
                clean,
                f"{clean} behind the scenes",
                f"{clean} production",
                f"{clean} visual effects",
                f"{clean} filmmaking",
            ],

            "cinematic_movie_edit": [
                clean,
                f"{clean} cinematic",
                f"{clean} film",
                f"{clean} scene",
                f"{clean} production",
            ],

            "curiosity_story": [
                clean,
                f"{clean} documentary",
                f"{clean} real footage",
                f"{clean} location",
                f"{clean} archive footage",
            ],

            "luxury_product": [
                clean,
                f"{clean} product",
                f"{clean} close up",
                f"{clean} manufacturing",
                f"{clean} craftsmanship",
                f"{clean} detail",
            ],

            "science_explainer": [
                science_subject,
                clean,
                f"{science_subject} demonstration",
                f"{science_subject} mechanism",
                f"{science_subject} engineering",
                f"{science_subject} animation",
            ],

            "business_wealth": [
                clean,
                f"{clean} company",
                f"{clean} founder",
                f"{clean} headquarters",
                f"{clean} products",
                f"{clean} archive",
            ],
        }

        raw = format_queries.get(
            format_name,
            [
                clean,
            ],
        )

        # NASA's catalog titles use mission-language rather than the wording
        # of a social-video hook.  These variants expose official alignment
        # and deployment footage as additional candidates while strict CLIP
        # matching still decides whether any individual shot is relevant.
        if (
            format_name == "science_explainer"
            and "james webb space telescope" in science_subject.lower()
        ):
            raw = [
                *raw,
                "James Webb Space Telescope mirror alignment",
                "James Webb Space Telescope launch deployment",
            ]

        output = []
        seen = set()

        for query in raw:

            normalized = " ".join(
                str(query).split()
            ).strip()

            key = normalized.lower()

            if (
                not normalized
                or key in seen
            ):
                continue

            seen.add(key)
            output.append(
                normalized
            )

        return output
