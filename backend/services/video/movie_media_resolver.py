"""Rights-aware media resolution for movie commentary."""

from __future__ import annotations

import asyncio

from dataclasses import asdict, dataclass

from backend.services.storyboard.movie_visual_beat_planner import (
    MovieVisualBeat,
)
from backend.services.video.movie_contextual_query_builder import (
    MovieContextualQueryBuilder,
)

from backend.services.video.asset_collector import AssetCollector
from backend.services.video.media_asset import MediaAsset
from backend.services.video.media_sources.wikimedia import (
    WikimediaCommonsProvider,
)
from backend.services.video.media_sources.pexels import (
    PexelsProvider,
)
from backend.services.video.visual_semantic_validator import (
    VisualSemanticValidator,
)
from backend.services.video.visual_quality_validator import (
    VisualQualityValidator,
)


@dataclass(slots=True)
class ResolvedMovieBeat:
    beat_id: str
    narration_index: int
    purpose: str
    visual_query: str
    target_duration: float
    evidence_ids: list[str]

    asset: MediaAsset | None
    status: str
    attempted_queries: list[str]

    def to_dict(self) -> dict:
        data = asdict(self)

        if self.asset is not None:
            data["asset"] = asdict(
                self.asset
            )

        return data


class MovieMediaResolver:
    """
    Resolve movie visual beats to production-authorized media.

    Search availability is never treated as reuse permission.

    Every selected asset must:
        - exist locally
        - identify its source
        - identify its license
        - permit commercial reuse
        - pass relevance validation
        - match the production content_id

    Copyrighted movie footage is not acquired from streaming
    platforms, YouTube uploads, or other unauthorized sources.
    """

    MAX_QUERY_VARIANTS = 3
    RESULTS_PER_QUERY = 1

    def __init__(
        self,
        *,
        providers=None,
        asset_collector=None,
    ) -> None:

        self.providers = (
            providers
            if providers is not None
            else [
                WikimediaCommonsProvider(),
                PexelsProvider(),
            ]
        )

        self.asset_collector = (
            asset_collector
            if asset_collector is not None
            else AssetCollector()
        )

        self.visual_semantic_validator = (
            VisualSemanticValidator()
        )

        self.visual_quality_validator = (
            VisualQualityValidator()
        )

    async def resolve(
        self,
        *,
        beats: list[MovieVisualBeat],
        content_id: str,
        movie_title: str,
    ) -> list[ResolvedMovieBeat]:

        if not beats:
            raise RuntimeError(
                "MovieMediaResolver received no beats."
            )

        clean_content_id = str(
            content_id
        ).strip()

        if not clean_content_id:
            raise RuntimeError(
                "Movie media resolution requires content_id."
            )

        used_source_urls: set[str] = set()

        resolved: list[ResolvedMovieBeat] = []

        for beat in beats:

            queries = self._query_variants(
                beat=beat,
                movie_title=movie_title,
            )

            candidates: list[MediaAsset] = []

            for query in queries[
                :self.MAX_QUERY_VARIANTS
            ]:

                for provider in self.providers:

                    try:
                        found = await provider.search_and_download(
                            query=query,
                            content_id=clean_content_id,
                            limit=self.RESULTS_PER_QUERY,
                        )
                    except Exception:
                        # Provider failure is isolated to this
                        # query/provider combination.
                        continue

                    for asset in found:

                        if (
                            asset.source_url
                            in used_source_urls
                        ):
                            continue

                        self._apply_query_relevance(
                            asset=asset,
                            query=query,
                            beat=beat,
                            movie_title=movie_title,
                        )

                        valid, issues = (
                            self.asset_collector.validate_asset(
                                asset,
                                content_id=clean_content_id,
                            )
                        )

                        if not valid:
                            continue

                        if not self._passes_identity_policy(
                            asset=asset,
                            beat=beat,
                            query=query,
                            movie_title=movie_title,
                        ):
                            continue

                        visual_validation = await asyncio.to_thread(
                            self.visual_semantic_validator.validate,
                            asset=asset,
                            beat=beat,
                            movie_title=movie_title,
                        )

                        if not visual_validation["valid"]:
                            continue

                        quality_validation = await asyncio.to_thread(
                            self.visual_quality_validator.validate,
                            asset=asset,
                        )

                        if not quality_validation["valid"]:
                            continue


                        candidates.append(
                            asset
                        )


            winner = self._select_best(
                candidates
            )

            ####################################################
            # Second-stage unresolved fallback
            #
            # Only spend additional provider/API work when the
            # primary candidate pool produced no valid winner.
            ####################################################

            if winner is None:

                fallback_candidates: list[MediaAsset] = []

                fallback_queries = queries[
                    self.MAX_QUERY_VARIANTS:
                ]

                for query in fallback_queries:

                    for provider in self.providers:

                        try:
                            found = await provider.search_and_download(
                                query=query,
                                content_id=clean_content_id,
                                limit=self.RESULTS_PER_QUERY,
                            )

                        except Exception:
                            continue

                        for asset in found:

                            if (
                                asset.source_url
                                in used_source_urls
                            ):
                                continue

                            self._apply_query_relevance(
                                asset=asset,
                                query=query,
                                beat=beat,
                                movie_title=movie_title,
                            )

                            valid, issues = (
                                self.asset_collector.validate_asset(
                                    asset,
                                    content_id=clean_content_id,
                                )
                            )

                            if not valid:
                                continue

                            if not self._passes_identity_policy(
                                asset=asset,
                                beat=beat,
                                query=query,
                                movie_title=movie_title,
                            ):
                                continue

                            visual_validation = await asyncio.to_thread(
                                self.visual_semantic_validator.validate,
                                asset=asset,
                                beat=beat,
                                movie_title=movie_title,
                            )

                            if not visual_validation["valid"]:
                                continue

                            quality_validation = await asyncio.to_thread(
                                self.visual_quality_validator.validate,
                                asset=asset,
                            )

                            if not quality_validation["valid"]:
                                continue


                            fallback_candidates.append(
                                asset
                            )

                    # Stop after the first fallback query that
                    # yields authorized candidates. Unlike the
                    # primary pool, this stage exists only to
                    # recover an otherwise unresolved beat.
                    if fallback_candidates:
                        break

                winner = self._select_best(
                    fallback_candidates
                )


            if winner is None:

                resolved.append(
                    ResolvedMovieBeat(
                        beat_id=beat.beat_id,
                        narration_index=(
                            beat.narration_index
                        ),
                        purpose=beat.purpose,
                        visual_query=beat.visual_query,
                        target_duration=(
                            beat.target_duration
                        ),
                        evidence_ids=list(
                            beat.evidence_ids
                        ),
                        asset=None,
                        status="unresolved",
                        attempted_queries=queries,
                    )
                )

                continue

            used_source_urls.add(
                winner.source_url
            )

            resolved.append(
                ResolvedMovieBeat(
                    beat_id=beat.beat_id,
                    narration_index=(
                        beat.narration_index
                    ),
                    purpose=beat.purpose,
                    visual_query=beat.visual_query,
                    target_duration=(
                        beat.target_duration
                    ),
                    evidence_ids=list(
                        beat.evidence_ids
                    ),
                    asset=winner,
                    status="resolved",
                    attempted_queries=queries,
                )
            )

        return resolved

    @staticmethod
    def _passes_identity_policy(
        *,
        asset: MediaAsset,
        beat: MovieVisualBeat,
        query: str,
        movie_title: str,
    ) -> bool:
        """
        Prevent generic stock media from impersonating a specific
        filmmaker or named movie identity.

        Pexels may still satisfy these beats through contextual
        fallback queries such as "film director on set".
        """

        if (
            str(
                asset.source_name
            ).strip().lower()
            != "pexels"
        ):
            return True

        clean_query = " ".join(
            str(query).lower().split()
        )

        clean_movie = " ".join(
            str(movie_title).lower().split()
        )

        visual_text = " ".join(
            str(
                beat.visual_query
            ).lower().split()
        )

        identity_words = {
            "director",
            "directing",
            "filmmaker",
        }

        has_identity_intent = any(
            word in visual_text
            for word in identity_words
        )

        if (
            has_identity_intent
            and clean_movie
            and clean_movie in clean_query
        ):
            return False

        return True

    @staticmethod
    def _apply_query_relevance(
        *,
        asset: MediaAsset,
        query: str,
        beat: MovieVisualBeat,
        movie_title: str,
    ) -> None:
        """
        Apply resolver-level retrieval relevance.

        Direct movie-specific matches receive the strongest
        retrieval confidence.

        Contextual Pexels results may enter the candidate pool,
        but do not outrank stronger direct matches merely because
        they are video.
        """

        current = float(
            asset.relevance_score
            or 0.0
        )

        clean_query = " ".join(
            str(query).lower().split()
        )

        clean_visual = " ".join(
            str(
                beat.visual_query
            ).lower().split()
        )

        clean_movie = " ".join(
            str(movie_title).lower().split()
        )

        score = current

        ####################################################
        # Exact planned visual request
        ####################################################

        if (
            clean_visual
            and clean_query == clean_visual
        ):
            score = max(
                score,
                78.0,
            )

        ####################################################
        # Movie-specific retrieval
        ####################################################

        elif (
            clean_movie
            and clean_movie in clean_query
        ):
            score = max(
                score,
                72.0,
            )

        ####################################################
        # Contextual provider retrieval
        ####################################################

        if (
            str(
                asset.source_name
            ).strip().lower()
            == "pexels"
        ):
            score = max(
                score,
                68.0,
            )

        ####################################################
        # Purpose/query alignment
        ####################################################

        purpose_terms = {
            "hook_subject": {
                "film",
                "mirror",
                "dimension",
                "cinematic",
                "surreal",
            },
            "hook_detail": {
                "visual",
                "effects",
                "geometry",
                "surreal",
                "cinematic",
            },
            "filmmaker_context": {
                "director",
                "film",
                "production",
                "camera",
                "filmmaking",
            },
            "explanation": {
                "production",
                "dimension",
                "action",
                "film",
                "behind",
            },
            "technical_detail": {
                "visual",
                "effects",
                "vfx",
                "compositing",
                "graphics",
            },
            "supporting_visual": {
                "visual",
                "effects",
                "production",
                "surreal",
                "geometry",
            },
            "payoff": {
                "cinematic",
                "action",
                "film",
                "city",
                "visual",
            },
            "closing_visual": {
                "visual",
                "effects",
                "cinematic",
                "dimension",
                "geometry",
            },
        }

        expected = purpose_terms.get(
            beat.purpose,
            set(),
        )

        query_words = set(
            clean_query.split()
        )

        overlap = len(
            expected.intersection(
                query_words
            )
        )

        if overlap >= 2:
            score += 4.0

        elif overlap == 1:
            score += 2.0

        asset.relevance_score = round(
            min(
                score,
                95.0,
            ),
            1,
        )

    @staticmethod
    def _select_best(
        candidates: list[MediaAsset],
    ) -> MediaAsset | None:

        if not candidates:
            return None

        ranked = sorted(
            candidates,
            key=lambda asset: (
                ################################################
                # Relevance is always the primary criterion.
                ################################################
                float(
                    asset.relevance_score
                    or 0.0
                ),

                ################################################
                # Prefer motion only after relevance.
                ################################################
                asset.asset_type == "video",

                ################################################
                # Portrait assets fit Shorts better.
                ################################################
                (
                    (asset.height or 0)
                    >
                    (asset.width or 0)
                ),

                ################################################
                # Resolution is only a final tie-breaker.
                ################################################
                (
                    (asset.width or 0)
                    *
                    (asset.height or 0)
                ),
            ),
            reverse=True,
        )

        return ranked[0]

    @staticmethod
    def _query_variants(
        *,
        beat: MovieVisualBeat,
        movie_title: str,
    ) -> list[str]:

        ####################################################
        # Tier 1: direct movie/context searches
        ####################################################

        primary = " ".join(
            beat.visual_query.split()
        ).strip()

        direct_queries = [
            primary,
        ]

        purpose_queries = {
            "hook_subject": [
                f"{movie_title} film",
                f"{movie_title} promotional image",
            ],
            "hook_detail": [
                f"{movie_title} visual effects",
                f"{movie_title} production still",
            ],
            "filmmaker_context": [
                f"{movie_title} director",
                f"{movie_title} production",
            ],
            "explanation": [
                f"{movie_title} behind the scenes",
                f"{movie_title} production still",
            ],
            "technical_detail": [
                f"{movie_title} visual effects",
                f"{movie_title} VFX production",
            ],
            "supporting_visual": [
                f"{movie_title} production image",
                f"{movie_title} film still",
            ],
            "payoff": [
                f"{movie_title} film",
                f"{movie_title} promotional image",
            ],
            "closing_visual": [
                f"{movie_title} visual effects",
                f"{movie_title} production still",
            ],
        }

        direct_queries.extend(
            purpose_queries.get(
                beat.purpose,
                [],
            )
        )

        ####################################################
        # Tier 2: contextual licensed B-roll
        ####################################################

        contextual_queries = (
            MovieContextualQueryBuilder.build(
                visual_query=beat.visual_query,
                purpose=beat.purpose,
            )
        )

        ####################################################
        # Preserve order:
        #
        # direct movie relevance first,
        # broader contextual fallback second.
        ####################################################

        queries = (
            direct_queries
            + contextual_queries
        )

        output = []
        seen = set()

        for query in queries:

            clean = " ".join(
                str(query).split()
            ).strip()

            key = clean.lower()

            if (
                not clean
                or key in seen
            ):
                continue

            seen.add(key)
            output.append(clean)

        return output



