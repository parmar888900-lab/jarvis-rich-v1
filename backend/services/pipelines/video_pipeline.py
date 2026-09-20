import asyncio
"""
Rich V1 video production pipeline.

Responsibilities:
    - Generate grounded content
    - Validate/repair content
    - Build narration storyboard
    - Acquire real licensed media
    - Validate media provenance and relevance
    - Build production package
    - Render final video

AI-generated imagery is no longer the primary visual source.
"""

import re
from pathlib import Path

from backend.services.content_generator import ContentGenerator
from backend.services.content_validator import ContentValidator
from backend.services.intelligence.content_format_classifier import ContentFormatClassifier
from backend.services.intelligence.movie_topic_parser import MovieTopicParser
from backend.services.research.evergreen_research_service import EvergreenResearchService
from backend.services.research.movie_research_service import MovieResearchService
from backend.services.storyboard.generator import StoryboardGenerator
# RICH_V1_MOVIE_MEDIA_V6_3
from backend.services.storyboard.movie_visual_beat_planner import (
    MovieVisualBeatPlanner,
)
from backend.services.video.movie_media_resolver import (
    MovieMediaResolver,
)
from backend.services.video.asset_collector import AssetCollector
from backend.services.video.media_query_builder import MediaQueryBuilder
from backend.services.video.media_sources.wikimedia import (
    WikimediaCommonsProvider,
)
from backend.services.video.production_package import (
    ProductionPackageBuilder,
)
from backend.services.video.visual_beat_planner import VisualBeatPlanner
from backend.services.video.source_footage_resolver import (
    SourceFootageResolver,
)
from backend.services.video_renderer.renderer import VideoRenderer
from backend.services.video.media_asset import media_provenance_identity


# RICH_V1_REAL_VIDEO_V6_1
from backend.services.video.source_clip_indexer import (
    SourceClipIndexer,
)
from backend.services.video.strict_clip_matcher import (
    StrictClipMatcher,
)
from backend.services.video.visual_beat_source_planner import (
    SourceVisualBeat,
)


class VideoPipeline:

    MIN_ASSETS_PER_SCENE = 1
    TARGET_ASSETS_PER_SCENE = 1

    # Stage media remains mandatory and rights-validated.
    # Beat-level provider searches are optional enrichment.
    MAX_SEMANTIC_MEDIA_ENRICHMENTS = 10

    # MASTER_VISUAL_ACQUISITION_V2
    STAGE_MEDIA_CANDIDATE_LIMIT = 3
    BEAT_MEDIA_CANDIDATE_LIMIT = 3
    TARGET_DISTINCT_BEAT_ASSETS = 6
    SEMANTIC_VISUAL_V4 = True
    REFERENCE_VISUAL_V5 = True

    def __init__(self):

        self.generator = ContentGenerator()
        self.content_validator = ContentValidator()
        self.research_service = EvergreenResearchService()
        self.movie_research_service = MovieResearchService()
        self.format_classifier = ContentFormatClassifier()
        self.storyboard = StoryboardGenerator()

        self.media_provider = (
            WikimediaCommonsProvider()
        )

        self.asset_collector = AssetCollector()
        self.media_query_builder = MediaQueryBuilder()

        self.visual_beat_planner = VisualBeatPlanner()

        # RICH_V1_MOVIE_MEDIA_V6_3
        self.movie_visual_beat_planner = MovieVisualBeatPlanner()
        self.movie_media_resolver = MovieMediaResolver()

        # RICH_V1_VIDEO_ACQUISITION_V6_2
        #
        # Existing rights-aware resolver:
        # Wikimedia / Internet Archive -> Pexels fallback.
        # It validates assets before returning video footage.
        self.source_footage_resolver = SourceFootageResolver()

        self.package_builder = (
            ProductionPackageBuilder()
        )

        self.renderer = VideoRenderer()


    # MASTER_VISUAL_HELPERS_V2

    @staticmethod
    def _master_asset_identity(asset) -> str:

        if asset is None:
            return ""

        for attribute in (
            "local_path",
            "source_url",
            "asset_id",
        ):

            value = getattr(
                asset,
                attribute,
                None,
            )

            if value:
                return (
                    str(value)
                    .strip()
                    .lower()
                )

        if isinstance(asset, dict):

            for key in (
                "local_path",
                "source_url",
                "asset_id",
            ):

                value = asset.get(key)

                if value:
                    return (
                        str(value)
                        .strip()
                        .lower()
                    )

        return (
            str(asset)
            .strip()
            .lower()
        )

    @staticmethod
    def _master_query_tokens(
        value: str,
    ) -> set[str]:

        stop = {
            "about",
            "after",
            "again",
            "also",
            "because",
            "before",
            "being",
            "could",
            "does",
            "from",
            "have",
            "into",
            "movie",
            "movies",
            "often",
            "some",
            "that",
            "their",
            "there",
            "these",
            "they",
            "this",
            "those",
            "through",
            "using",
            "very",
            "what",
            "when",
            "where",
            "which",
            "while",
            "with",
            "would",
        }

        words = re.findall(
            r"[A-Za-z0-9][A-Za-z0-9'-]+",
            str(value).lower(),
        )

        return {
            word
            for word in words
            if len(word) >= 4
            and word not in stop
        }

    @classmethod
    def _master_query_variants(
        cls,
        *,
        topic,
        beat,
    ):
        """
        REFERENCE_VISUAL_V5

        Translate a narration beat into concrete visual actions
        rather than generic topic searches.

        Provider requests stay bounded. The highest-value literal
        visual requirements are always attempted first.
        """

        def clean(value):
            return " ".join(
                str(value or "").strip().split()
            )

        def tokens(value):
            return {
                token.lower()
                for token in clean(value).split()
                if len(token) >= 3
            }

        search_query = clean(
            getattr(
                beat,
                "search_query",
                "",
            )
        )

        visual_requirement = clean(
            getattr(
                beat,
                "visual_requirement",
                "",
            )
        )

        purpose = clean(
            getattr(
                beat,
                "purpose",
                "",
            )
        )

        beat_text = " ".join(
            part
            for part in (
                visual_requirement,
                search_query,
                purpose,
            )
            if part
        )

        lower = beat_text.lower()

        beat_words = {
            token.strip(".,:;!?()[]{}-_/'""")
            for token in lower.split()
            if token.strip(".,:;!?()[]{}-_/'""")
        }

        queries = []

        def add(query):
            query = clean(query)

            if not query:
                return

            key = query.lower()

            if key not in {
                existing.lower()
                for existing in queries
            }:
                queries.append(query)

        # ====================================================
        # LITERAL FOLEY MECHANISMS
        # ====================================================

        if any(
            word in beat_words
            for word in (
                "footstep",
                "footsteps",
                "shoe",
                "shoes",
                "walking",
                "walk",
                "floor",
            )
        ):
            add(
                "Foley artist recording footsteps "
                "shoes floor film studio"
            )
            add(
                "film Foley footsteps shoes "
                "sound effects stage"
            )
            add(
                "Foley performer footsteps "
                "movie sound recording"
            )

        elif any(
            word in beat_words
            for word in (
                "prop",
                "props",
                "object",
                "objects",
                "door",
                "cloth",
                "clothes",
                "fabric",
                "glass",
                "metal",
                "wood",
                "paper",
            )
        ):
            add(
                "Foley artist using props "
                "movie sound effects studio"
            )
            add(
                "hands Foley props film "
                "sound recording"
            )
            add(
                "Foley stage objects props "
                "sound effects"
            )

        elif any(
            word in beat_words
            for word in (
                "adr",
                "dialogue",
                "dialog",
                "voice",
                "actor",
                "speech",
                "line",
                "lines",
            )
        ):
            add(
                "actor ADR dialogue recording "
                "film microphone studio"
            )
            add(
                "film ADR booth actor "
                "dialogue microphone"
            )
            add(
                "movie dialogue replacement "
                "recording studio"
            )

        elif any(
            word in beat_words
            for word in (
                "edit",
                "editing",
                "editor",
                "post",
                "timeline",
                "waveform",
                "mix",
                "mixing",
                "layer",
                "layers",
            )
        ):
            add(
                "film sound editor audio waveform "
                "post production workstation"
            )
            add(
                "movie sound design editing "
                "timeline workstation"
            )
            add(
                "film audio post production "
                "sound editor mixing"
            )

        elif any(
            word in beat_words
            for word in (
                "microphone",
                "mic",
                "record",
                "recorded",
                "recording",
                "studio",
            )
        ):
            add(
                "Foley artist recording movie "
                "sound effects microphone"
            )
            add(
                "film Foley recording stage "
                "microphone sound effects"
            )
            add(
                "professional Foley performer "
                "film sound studio"
            )

        elif any(
            word in beat_words
            for word in (
                "ambient",
                "ambience",
                "environment",
                "outside",
                "field",
                "nature",
                "background",
            )
        ):
            add(
                "film field recording ambience "
                "professional microphone"
            )
            add(
                "sound recordist field recording "
                "movie ambience"
            )

        # ====================================================
        # USE THE PLANNER'S EXACT VISUAL REQUIREMENT
        #
        # Keep it concrete by adding the filmmaking context.
        # ====================================================

        if visual_requirement:
            add(
                visual_requirement
                + " film Foley sound effects"
            )

        if search_query:
            add(
                search_query
                + " film Foley"
            )

        # ====================================================
        # SAFE DOMAIN FALLBACK
        #
        # Deliberately NOT:
        #   recording room
        #   content creator
        #   studio person
        #
        # Those searches produced the ring-light imagery.
        # ====================================================

        add(
            "Foley artist performing "
            "movie sound effects studio"
        )

        add(
            "film Foley stage professional "
            "sound effects recording"
        )

        # Only expose the strongest variants to the provider.
        # This preserves bounded provider/API work.
        return queries[:3]


    @classmethod
    def _master_metadata_score(
        cls,
        *,
        asset,
        query,
        topic,
    ):
        """
        REFERENCE_VISUAL_V5

        Score literal metadata correspondence.

        Query/beat correspondence dominates topic-level overlap.
        """

        def normalize(value):
            return " ".join(
                str(value or "").lower().split()
            )

        def token_set(value):
            return {
                token.strip(
                    ".,:;!?()[]{}-_/"
                )
                for token in normalize(value).split()
                if len(
                    token.strip(
                        ".,:;!?()[]{}-_/"
                    )
                ) >= 3
            }

        metadata_parts = []

        for attr in (
            "title",
            "description",
            "source_url",
            "asset_id",
            "file_path",
            "local_path",
            "source_name",
        ):
            value = getattr(
                asset,
                attr,
                "",
            )

            if value:
                metadata_parts.append(
                    str(value)
                )

        metadata = normalize(
            " ".join(metadata_parts)
        )

        if not metadata:
            return 0.0

        query_tokens = token_set(query)
        topic_tokens = token_set(topic)
        metadata_tokens = token_set(metadata)

        if not metadata_tokens:
            return 0.0

        query_overlap = len(
            query_tokens & metadata_tokens
        )

        topic_overlap = len(
            topic_tokens & metadata_tokens
        )

        query_score = (
            query_overlap
            / max(
                1,
                len(query_tokens),
            )
        )

        topic_score = (
            topic_overlap
            / max(
                1,
                len(topic_tokens),
            )
        )

        # Literal visual intent matters substantially more than
        # merely matching the broad topic.
        score = (
            query_score * 0.86
            + topic_score * 0.14
        )

        # Domain evidence.
        domain_tokens = {
            "foley",
            "film",
            "movie",
            "cinema",
            "sound",
            "audio",
            "microphone",
            "recording",
            "editor",
            "editing",
            "production",
            "footsteps",
            "props",
            "dialogue",
            "waveform",
            "mixing",
        }

        domain_overlap = len(
            metadata_tokens & domain_tokens
        )

        if domain_overlap >= 3:
            score += 0.12

        elif domain_overlap >= 2:
            score += 0.07

        elif domain_overlap == 1:
            score += 0.025

        # Highly undesirable imagery discovered in the actual
        # V3/V4 benchmark renders.
        negative_tokens = {
            "selfie",
            "vlog",
            "vlogger",
            "blogger",
            "webcam",
            "streamer",
            "streaming",
            "influencer",
            "portrait",
            "fashion",
            "makeup",
            "ringlight",
            "ring-light",
            "livestream",
            "podcast",
            "podcaster",
            "youtuber",
            "creator",
        }

        negative_overlap = len(
            metadata_tokens & negative_tokens
        )

        score -= (
            negative_overlap * 0.24
        )

        return max(
            0.0,
            min(
                1.0,
                float(score),
            ),
        )


    @classmethod
    def _master_choose_asset(
        cls,
        *,
        candidates,
        query,
        topic,
        used_identities,
        previous_identity,
    ):
        """
        REFERENCE_VISUAL_V5

        Select literal, domain-relevant, non-repetitive media.

        Generic social-media studio imagery is rejected instead
        of being rewarded simply because it contains a microphone.
        """

        if not candidates:
            return None

        def normalize(value):
            return " ".join(
                str(value or "").lower().split()
            )

        def token_set(value):
            return {
                token.strip(
                    ".,:;!?()[]{}-_/"
                )
                for token in normalize(value).split()
                if len(
                    token.strip(
                        ".,:;!?()[]{}-_/"
                    )
                ) >= 3
            }

        domain_tokens = {
            "foley",
            "film",
            "movie",
            "cinema",
            "sound",
            "audio",
            "microphone",
            "recording",
            "editor",
            "editing",
            "production",
            "footsteps",
            "shoes",
            "props",
            "dialogue",
            "adr",
            "waveform",
            "mixing",
        }

        negative_tokens = {
            "selfie",
            "vlog",
            "vlogger",
            "blogger",
            "webcam",
            "streamer",
            "streaming",
            "influencer",
            "portrait",
            "fashion",
            "makeup",
            "ringlight",
            "ring-light",
            "livestream",
            "podcast",
            "podcaster",
            "youtuber",
            "creator",
        }

        ranked = []

        for asset in candidates:

            identity = (
                cls._master_asset_identity(
                    asset
                )
            )

            metadata = " ".join(
                str(
                    getattr(
                        asset,
                        attr,
                        "",
                    )
                    or ""
                )
                for attr in (
                    "title",
                    "description",
                    "source_url",
                    "asset_id",
                    "file_path",
                    "local_path",
                    "source_name",
                )
            )

            metadata_tokens = token_set(
                metadata
            )

            semantic_score = (
                cls._master_metadata_score(
                    asset=asset,
                    query=query,
                    topic=topic,
                )
            )

            domain_overlap = len(
                metadata_tokens
                & domain_tokens
            )

            negative_overlap = len(
                metadata_tokens
                & negative_tokens
            )

            score = float(
                semantic_score
            )

            # New material is strongly preferred.
            if (
                identity
                and identity
                not in used_identities
            ):
                score += 0.25

            # Prevent immediate visual repetition.
            if (
                identity
                and identity
                == previous_identity
            ):
                score -= 0.70

            # Domain relevance.
            if domain_overlap >= 3:
                score += 0.20

            elif domain_overlap == 2:
                score += 0.12

            elif domain_overlap == 1:
                score += 0.04

            # Generic creator imagery receives a very large
            # penalty because it dominated the V4 benchmark.
            score -= (
                negative_overlap * 0.45
            )

            ranked.append(
                (
                    score,
                    semantic_score,
                    domain_overlap,
                    negative_overlap,
                    identity,
                    asset,
                )
            )

        ranked.sort(
            key=lambda row: (
                row[0],
                row[1],
                row[2],
            ),
            reverse=True,
        )

        # ====================================================
        # TIER 1
        # Literal + domain relevant + unused.
        # ====================================================

        for (
            score,
            semantic_score,
            domain_overlap,
            negative_overlap,
            identity,
            asset,
        ) in ranked:

            if (
                identity
                and identity
                != previous_identity
                and identity
                not in used_identities
                and negative_overlap == 0
                and semantic_score >= 0.30
                and domain_overlap >= 2
            ):
                return asset

        # ====================================================
        # TIER 2
        # Still require meaningful semantic correspondence.
        # ====================================================

        for (
            score,
            semantic_score,
            domain_overlap,
            negative_overlap,
            identity,
            asset,
        ) in ranked:

            if (
                identity
                and identity
                != previous_identity
                and negative_overlap == 0
                and semantic_score >= 0.36
                and domain_overlap >= 1
            ):
                return asset

        # ====================================================
        # TIER 3
        #
        # Do NOT force a generic candidate.
        # Returning None lets the pipeline use its authorized
        # fallback path and lets Block 5 reject bad sequences.
        # ====================================================

        return None



    # ========================================================
    # RICH_V1_VIDEO_ACQUISITION_V6_2
    # ========================================================

    async def _v62_acquire_source_footage(
        self,
        *,
        format_name: str,
        topic: str,
        content_id: str,
    ) -> dict:
        """
        Existing SourceFootageResolver -> authorized video pool.

        This is deliberately separate from the V5 image path.
        Failure here must never remove the existing authorized
        image fallback.
        """

        try:
            result = await self.source_footage_resolver.resolve(
                format_name=str(format_name or "").strip(),
                topic=str(topic or "").strip(),
                content_id=str(content_id),
                minimum_assets=4,
                target_assets=8,
            )
        except Exception as exc:
            return {
                "status": "fallback_images",
                "reason": (
                    "source_footage_resolver:"
                    + type(exc).__name__
                ),
                "assets": [],
                "asset_count": 0,
                "primary_count": 0,
                "fallback_count": 0,
                "attempted_queries": [],
            }

        assets = [
            asset
            for asset in list(
                getattr(result, "assets", []) or []
            )
            if getattr(
                asset,
                "asset_type",
                "",
            ) == "video"
        ]

        return {
            "status": str(
                getattr(
                    result,
                    "status",
                    "unresolved",
                )
            ),
            "reason": (
                "authorized_source_footage"
                if assets
                else "no_authorized_source_footage"
            ),
            "assets": assets,
            "asset_count": len(assets),
            "primary_count": len(
                list(
                    getattr(
                        result,
                        "primary_assets",
                        [],
                    )
                    or []
                )
            ),
            "fallback_count": len(
                list(
                    getattr(
                        result,
                        "fallback_assets",
                        [],
                    )
                    or []
                )
            ),
            "attempted_queries": list(
                getattr(
                    result,
                    "attempted_queries",
                    [],
                )
                or []
            ),
        }


    # ========================================================
    # RICH_V1_REAL_VIDEO_V6_1
    # ========================================================

    @staticmethod
    def _v61_make_source_beat(
        beat,
        beat_index: int,
    ):
        """
        Convert the current VisualBeat into the existing
        SourceVisualBeat contract used by StrictClipMatcher.

        Reflection is intentional here so optional fields can
        evolve without breaking the V5 image fallback.
        """

        import dataclasses

        try:
            source_fields = {
                field.name
                for field
                in dataclasses.fields(
                    SourceVisualBeat
                )
            }
        except Exception:
            return None

        beat_id = str(
            getattr(
                beat,
                "beat_id",
                "",
            )
            or f"beat_{beat_index + 1}"
        ).strip()

        visual_goal = str(
            getattr(
                beat,
                "visual_goal",
                "",
            )
            or getattr(
                beat,
                "visual_requirement",
                "",
            )
            or getattr(
                beat,
                "purpose",
                "",
            )
            or getattr(
                beat,
                "search_query",
                "",
            )
        ).strip()

        primary_query = str(
            getattr(
                beat,
                "search_query",
                "",
            )
            or visual_goal
        ).strip()

        values = {}

        if "beat_id" in source_fields:
            values["beat_id"] = beat_id

        if "visual_goal" in source_fields:
            values["visual_goal"] = visual_goal

        if "search_queries" in source_fields:

            queries = []

            raw_queries = getattr(
                beat,
                "search_queries",
                None,
            )

            if raw_queries:
                queries.extend(
                    str(item).strip()
                    for item in raw_queries
                    if str(item).strip()
                )

            if (
                primary_query
                and primary_query not in queries
            ):
                queries.insert(
                    0,
                    primary_query,
                )

            if not queries and visual_goal:
                queries.append(
                    visual_goal
                )

            values["search_queries"] = (
                queries[:4]
            )

        if "negative_visuals" in source_fields:

            negative = getattr(
                beat,
                "negative_visuals",
                None,
            )

            if negative:
                negative = [
                    str(item).strip()
                    for item in negative
                    if str(item).strip()
                ]
            else:
                negative = [
                    "generic stock footage",
                    "unrelated person talking to camera",
                    "irrelevant lifestyle footage",
                    "unrelated object footage",
                ]

            values[
                "negative_visuals"
            ] = negative

        # Copy compatible fields directly when available.
        for field_name in source_fields:

            if field_name in values:
                continue

            if hasattr(
                beat,
                field_name,
            ):
                values[field_name] = getattr(
                    beat,
                    field_name,
                )

        try:
            return SourceVisualBeat(
                **values
            )

        except Exception:
            return None


    def _v61_build_video_matches(
        self,
        *,
        media_groups,
        visual_beats,
        content_id: str,
    ) -> dict:
        """
        Existing authorized MediaAsset videos
            -> SourceClipIndexer
            -> StrictClipMatcher
            -> exact source timestamps.

        Failure at any point returns to V5 image rendering.
        """

        videos = []
        seen = set()

        # ----------------------------------------------------
        # Only use assets that already passed the production
        # acquisition/authorization layer.
        # ----------------------------------------------------

        for group in media_groups:

            for asset in group:

                if (
                    getattr(
                        asset,
                        "asset_type",
                        "",
                    )
                    != "video"
                ):
                    continue

                source_path = str(
                    getattr(
                        asset,
                        "file_path",
                        "",
                    )
                    or ""
                ).strip()

                if not source_path:
                    continue

                if not Path(
                    source_path
                ).exists():
                    continue

                identity = str(
                    getattr(
                        asset,
                        "asset_id",
                        "",
                    )
                    or source_path
                )

                if identity in seen:
                    continue

                seen.add(identity)
                videos.append(asset)

        if not videos:

            return {
                "status":
                    "fallback_images",

                "reason":
                    "no_authorized_video_assets",

                "authorized_video_assets":
                    0,

                "indexed_clips":
                    0,

                "matched_beats":
                    0,

                "matches":
                    [],
            }

        # ----------------------------------------------------
        # Index exact 1–3 second source moments.
        # ----------------------------------------------------

        try:

            indexer = SourceClipIndexer()

            clips = indexer.index_assets(
                assets=videos,
                content_id=content_id,
            )

        except Exception as exc:

            return {
                "status":
                    "fallback_images",

                "reason":
                    (
                        "source_clip_indexer:"
                        + type(exc).__name__
                    ),

                "authorized_video_assets":
                    len(videos),

                "indexed_clips":
                    0,

                "matched_beats":
                    0,

                "matches":
                    [],
            }

        if not clips:

            return {
                "status":
                    "fallback_images",

                "reason":
                    "no_indexed_video_clips",

                "authorized_video_assets":
                    len(videos),

                "indexed_clips":
                    0,

                "matched_beats":
                    0,

                "matches":
                    [],
            }

        source_beats = []
        index_by_beat_id = {}

        for zero_index, beat in enumerate(
            visual_beats
        ):

            source_beat = (
                self._v61_make_source_beat(
                    beat,
                    zero_index,
                )
            )

            if source_beat is None:
                continue

            source_beats.append(
                source_beat
            )

            # Renderer beat_index starts at 1.
            index_by_beat_id[
                str(source_beat.beat_id)
            ] = zero_index + 1

        if not source_beats:

            return {
                "status":
                    "fallback_images",

                "reason":
                    "source_beat_conversion_failed",

                "authorized_video_assets":
                    len(videos),

                "indexed_clips":
                    len(clips),

                "matched_beats":
                    0,

                "matches":
                    [],
            }

        # ----------------------------------------------------
        # Existing strict positive/negative CLIP matcher.
        # ----------------------------------------------------

        try:

            matcher = StrictClipMatcher()

            max_reuse_per_source = min(
                10,
                max(
                    3,
                    (
                        len(source_beats)
                        + len(videos)
                        - 1
                    )
                    // len(videos),
                ),
            )

            matches = matcher.match_many(
                beats=source_beats,
                clips=clips,
                # A long authoritative source can contain many
                # genuinely different shots. Clip IDs remain unique;
                # this limit only prevents one file from monopolizing
                # the sequence when several sources are available.
                max_reuse_per_source=max_reuse_per_source,
            )

        except Exception as exc:

            return {
                "status":
                    "fallback_images",

                "reason":
                    (
                        "strict_clip_matcher:"
                        + type(exc).__name__
                    ),

                "authorized_video_assets":
                    len(videos),

                "indexed_clips":
                    len(clips),

                "matched_beats":
                    0,

                "matches":
                    [],
            }

        renderer_matches = []

        for match in matches:

            beat_index = (
                index_by_beat_id.get(
                    str(match.beat_id)
                )
            )

            if beat_index is None:
                continue

            renderer_matches.append(
                {
                    "beat_index":
                        int(beat_index),

                    "beat_id":
                        str(match.beat_id),

                    "visual_goal":
                        str(
                            match.visual_goal
                        ),

                    "clip_id":
                        str(match.clip_id),

                    "source_path":
                        str(
                            match.source_path
                        ),

                    "source_name":
                        str(
                            match.source_name
                        ),

                    "start_time":
                        float(
                            match.start_time
                        ),

                    "end_time":
                        float(
                            match.end_time
                        ),

                    "duration":
                        float(
                            match.duration
                        ),

                    "positive_score":
                        float(
                            match.positive_score
                        ),

                    "negative_score":
                        float(
                            match.negative_score
                        ),

                    "final_score":
                        float(
                            match.final_score
                        ),
                }
            )

        return {
            "status":
                (
                    "video_matches_ready"
                    if renderer_matches
                    else "fallback_images"
                ),

            "reason":
                (
                    "strict_semantic_matches"
                    if renderer_matches
                    else "no_strict_matches"
                ),

            "authorized_video_assets":
                len(videos),

            "indexed_clips":
                len(clips),

            "matched_beats":
                len(renderer_matches),

            "matches":
                renderer_matches,
        }


    async def run(
        self,
        trend: dict,
    ) -> dict:

        ####################################################
        # 1. Content identity
        ####################################################

        content_id = str(
            trend.get(
                "content_id",
                "",
            )
        ).strip()

        if not content_id:
            raise RuntimeError(
                "Production topic has no content_id."
            )

        ####################################################
        # 2. Choose production format
        ####################################################

        topic_title = str(
            trend.get(
                "title",
                "",
            )
        ).strip()

        genre = str(
            trend.get(
                "genre",
                "",
            )
        ).strip()

        format_decision = (
            self.format_classifier.classify(
                topic=topic_title,
                genre=genre,
                authorized_movie_source=False,
            )
        )

        trend["content_format"] = {
            "format_name": format_decision.format_name,
            "target_duration_min": format_decision.target_duration_min,
            "target_duration_max": format_decision.target_duration_max,
            "preferred_media": format_decision.preferred_media,
            "narration_mode": format_decision.narration_mode,
            "pacing": format_decision.pacing,
            "rights_gate_required": format_decision.rights_gate_required,
            "reference_profile": format_decision.reference_profile,
        }

        ####################################################
        # 3. Research topic
        ####################################################

        if (
            format_decision.format_name
            == "famous_movie_commentary"
        ):

            movie_title = (
                MovieTopicParser.extract_movie_title(
                    topic_title
                )
            )

            if not movie_title:
                raise RuntimeError(
                    "Movie commentary topic has no recognized "
                    f"movie title: {topic_title}"
                )

            trend["movie_title"] = movie_title

            knowledge_pack = await asyncio.to_thread(
                    self.movie_research_service.research,
                    movie_title=movie_title,
                    commentary_topic=topic_title,
                )

            research_text = (
                self.movie_research_service.build_research_text(
                    knowledge_pack
                )
            )

        else:

            knowledge_pack = await asyncio.to_thread(
                    self.research_service.research,
                    topic_title,
                )

            research_text = (
                self.research_service.build_research_text(
                    knowledge_pack
                )
            )

        if not research_text.strip():
            raise RuntimeError(
                "Research returned no usable grounded "
                f"information for: {topic_title}"
            )

        trend["research"] = research_text
        trend["knowledge"] = knowledge_pack.to_dict()

        ####################################################
        # 4. Generate content
        ####################################################
        generated = await self.generator.generate(
            trend
        )

        if generated is None:
            raise RuntimeError(
                "ContentGenerator returned None."
            )

        ####################################################
        # 3. Validate generated content
        ####################################################

        validation = (
            self.content_validator.validate(
                generated
            )
        )

        ####################################################
        # 4. Repair rejected content
        ####################################################

        if not validation["valid"]:

            repaired = await self.generator.repair(
                content=generated,
                trend=trend,
                issues=validation["issues"],
            )

            if repaired is None:
                raise RuntimeError(
                    "Generated content failed validation "
                    "and automatic repair failed."
                )

            repaired_validation = (
                self.content_validator.validate(
                    repaired
                )
            )

            if not repaired_validation["valid"]:
                raise RuntimeError(
                    "Repaired content still failed "
                    "validation: "
                    f"{repaired_validation['issues']}"
                )

            generated = repaired
            validation = repaired_validation

        ####################################################
        # 5. Build narration storyboard
        ####################################################

        storyboard = self.storyboard.generate(
            generated
        )

        if not storyboard:
            raise RuntimeError(
                "StoryboardGenerator produced no scenes."
            )

        ####################################################
        # 6. Acquire real licensed media
        ####################################################

        media_groups = []

        topic = str(
            trend.get(
                "title",
                "",
            )
        ).strip()

        genre = str(
            trend.get(
                "genre",
                "",
            )
        ).strip()

        ####################################################
        # Stage 2B - semantic visual micro-beats
        #
        # Narration remains four grounded story stages.
        # Visuals are planned independently at a denser cadence.
        ####################################################

        # RICH_V1_MOVIE_MEDIA_V6_3
        #
        # Famous-movie commentary uses its dedicated 14-beat
        # production grammar. Every other Rich V1 format retains
        # the existing generic VisualBeatPlanner unchanged.
        is_movie_commentary = (
            str(format_decision.format_name).strip()
            == "famous_movie_commentary"
        )

        movie_title = str(
            generated.metadata.get("movie_title", "")
            or trend.get("movie_title", "")
        ).strip()

        if is_movie_commentary:

            if not movie_title:
                raise RuntimeError(
                    "V6.3 movie production requires movie_title."
                )

            visual_beats = (
                self.movie_visual_beat_planner.plan(
                    content=generated,
                    movie_title=movie_title,
                    topic=topic,
                )
            )

            visual_beat_dicts = (
                self.movie_visual_beat_planner.to_dicts(
                    visual_beats
                )
            )

        else:

            visual_beats = self.visual_beat_planner.plan(
                content=generated,
                topic=topic,
                genre=genre,
                format_name=(
                    format_decision.format_name
                ),
            )

            visual_beat_dicts = (
                self.visual_beat_planner.to_dicts(
                    visual_beats
                )
            )

        if not visual_beats:
            raise RuntimeError(
                "Visual beat planner produced no visual beats."
            )

        for index, scene in enumerate(
            storyboard,
            start=1,
        ):

            queries = (
                self.media_query_builder.build(
                    topic=topic,
                    genre=genre,
                    narration=scene.narration,
                )
            )[:3]

            authorized_scene_assets = []

            for query in queries:

                found = await (
                    self.media_provider
                    .search_and_download(
                        query=query,
                        content_id=content_id,
                        limit=(
                            self.STAGE_MEDIA_CANDIDATE_LIMIT
                        ),
                    )
                )

                if not found:
                    continue

                try:
                    authorized = (
                        self.asset_collector.authorize(
                            found,
                            content_id=content_id,
                        )
                    )
                except RuntimeError:
                    continue

                for image_asset in authorized:

                    if (
                        image_asset.asset_type
                        != "image"
                    ):
                        continue

                    identity = (
                        self._master_asset_identity(
                            image_asset
                        )
                    )

                    existing_ids = {
                        self._master_asset_identity(
                            existing
                        )
                        for existing
                        in authorized_scene_assets
                    }

                    if (
                        identity
                        and identity
                        not in existing_ids
                    ):
                        authorized_scene_assets.append(
                            image_asset
                        )

                    if (
                        len(authorized_scene_assets)
                        >= self.STAGE_MEDIA_CANDIDATE_LIMIT
                    ):
                        break

                if (
                    len(authorized_scene_assets)
                    >= self.STAGE_MEDIA_CANDIDATE_LIMIT
                ):
                    break

            if not authorized_scene_assets:
                raise RuntimeError(
                    "Scene "
                    f"{index} produced no authorized "
                    "image after limited media search. "
                    f"Queries: {queries}"
                )

            media_groups.append(
                authorized_scene_assets
            )

        if (
            len(media_groups)
            != len(storyboard)
        ):
            raise RuntimeError(
                "Storyboard/media group mismatch."
            )
        ####################################################
        # Stage 2B - beat-specific authorized media
        #
        # IMPORTANT:
        # This layer is deliberately fail-soft.
        #
        # Every beat has a known-good authorized fallback from
        # its narration stage. A failed provider query therefore
        # reduces visual specificity instead of failing the video.
        ####################################################

        beat_render_assets = []
        beat_media_evidence = []

        semantic_enrichment_attempts = 0
        semantic_enrichment_successes = 0
        semantic_fallback_count = 0

        master_candidate_count = 0
        master_semantic_rejections = 0
        master_duplicate_avoidance_events = 0
        master_query_count = 0

        used_identities: set[str] = set()
        previous_identity = ""

        for beat_index, beat in enumerate(
            visual_beats
        ):

            narration_index = int(
                beat.narration_index
            )

            stage_index = max(
                0,
                min(
                    narration_index - 1,
                    len(media_groups) - 1,
                ),
            )

            stage_candidates = [
                asset
                for asset
                in media_groups[stage_index]
                if asset.asset_type == "image"
            ]

            if not stage_candidates:
                raise RuntimeError(
                    "Stage 2B fallback media missing for "
                    f"narration stage {narration_index}."
                )

            query_variants = (
                self._master_query_variants(
                    topic=topic,
                    beat=beat,
                )
            )

            primary_query = (
                query_variants[0]
                if query_variants
                else str(
                    beat.search_query
                ).strip()
            )

            selected_asset = None
            selected_via = ""
            authorized_candidates = []

            for query in query_variants:

                if (
                    semantic_enrichment_attempts
                    >= self.MAX_SEMANTIC_MEDIA_ENRICHMENTS
                ):
                    break

                semantic_enrichment_attempts += 1
                master_query_count += 1

                try:

                    found = await (
                        self.media_provider
                        .search_and_download(
                            query=query,
                            content_id=content_id,
                            limit=(
                                self.BEAT_MEDIA_CANDIDATE_LIMIT
                            ),
                        )
                    )

                except Exception:

                    found = []

                if not found:
                    continue

                try:

                    authorized = (
                        self.asset_collector.authorize(
                            found,
                            content_id=content_id,
                        )
                    )

                except RuntimeError:

                    authorized = []

                images = [
                    asset
                    for asset in authorized
                    if asset.asset_type == "image"
                ]

                master_candidate_count += len(
                    images
                )

                authorized_candidates.extend(
                    images
                )

                candidate = (
                    self._master_choose_asset(
                        candidates=images,
                        query=query,
                        topic=topic,
                        used_identities=(
                            used_identities
                        ),
                        previous_identity=(
                            previous_identity
                        ),
                    )
                )

                if candidate is not None:

                    selected_asset = candidate

                    selected_via = (
                        "semantic_query_diverse"
                    )

                    semantic_enrichment_successes += 1

                    break

                master_semantic_rejections += len(
                    images
                )

            if selected_asset is None:

                fallback_pool = list(
                    stage_candidates
                )

                if fallback_pool:

                    shift = (
                        beat_index
                        % len(fallback_pool)
                    )

                    fallback_pool = (
                        fallback_pool[shift:]
                        + fallback_pool[:shift]
                    )

                selected_asset = (
                    self._master_choose_asset(
                        candidates=fallback_pool,
                        query=primary_query,
                        topic=topic,
                        used_identities=(
                            used_identities
                        ),
                        previous_identity=(
                            previous_identity
                        ),
                    )
                )

                if selected_asset is None:

                    # SEMANTIC_VISUAL_V4:
                    # prefer a different authorized stage asset,
                    # but do not pretend it was semantically matched.
                    selected_asset = next(
                        (
                            asset
                            for asset
                            in fallback_pool
                            if (
                                self._master_asset_identity(
                                    asset
                                )
                                != previous_identity
                                and self._master_metadata_score(
                                    asset=asset,
                                    query=primary_query,
                                    topic=topic,
                                ) >= 0.12
                            )
                        ),
                        None,
                    )

                if selected_asset is None:

                    selected_asset = next(
                        (
                            asset
                            for asset
                            in fallback_pool
                            if (
                                self._master_asset_identity(
                                    asset
                                )
                                != previous_identity
                            )
                        ),
                        fallback_pool[0],
                    )

                selected_via = (
                    "semantic_rotating_stage_fallback"
                )

                semantic_fallback_count += 1

            identity = (
                self._master_asset_identity(
                    selected_asset
                )
            )

            if (
                identity
                and identity
                == previous_identity
            ):

                alternatives = (
                    authorized_candidates
                    + stage_candidates
                )

                replacement = next(
                    (
                        asset
                        for asset
                        in alternatives
                        if (
                            self._master_asset_identity(
                                asset
                            )
                            and self._master_asset_identity(
                                asset
                            )
                            != previous_identity
                        )
                    ),
                    None,
                )

                if replacement is not None:

                    master_duplicate_avoidance_events += 1

                    selected_asset = replacement

                    identity = (
                        self._master_asset_identity(
                            selected_asset
                        )
                    )

                    selected_via += (
                        "_duplicate_avoided"
                    )

            if identity:
                used_identities.add(
                    identity
                )

            previous_identity = identity

            beat_render_assets.append(
                selected_asset
            )

            beat_media_evidence.append(
                {
                    "beat_id": beat.beat_id,
                    "narration_index": narration_index,
                    "purpose": beat.purpose,
                    "query": primary_query,
                    "query_variants": query_variants,
                    "selected_via": selected_via,
                    "asset_id": selected_asset.asset_id,
                    "source_name": selected_asset.source_name,
                    "source_url": selected_asset.source_url,
                    "license_name": selected_asset.license_name,
                    "commercial_use_allowed": (
                        selected_asset
                        .commercial_use_allowed
                    ),
                }
            )

        if (
            len(beat_render_assets)
            != len(visual_beats)
        ):
            raise RuntimeError(
                "Visual beat/media timeline mismatch."
            )

        ####################################################
        # 7. Temporary renderer compatibility
        #
        # The existing renderer still accepts one image
        # object per narration scene. For this integration
        # test we pass the strongest authorized IMAGE from
        # each group.
        #
        # The next renderer patch will consume the complete
        # media_groups structure and produce multiple cuts.
        ####################################################

        render_assets = []

        for index, group in enumerate(
            media_groups,
            start=1,
        ):

            image_asset = next(
                (
                    asset
                    for asset in group
                    if asset.asset_type
                    == "image"
                ),
                None,
            )

            if image_asset is None:
                raise RuntimeError(
                    "Scene "
                    f"{index} has no image-compatible "
                    "asset for the current renderer."
                )

            render_assets.append(
                image_asset
            )

        ####################################################
        # 8. Build production package
        ####################################################


        # ====================================================
        # RICH_V1_REAL_VIDEO_V6_1
        # ====================================================

        # ====================================================
        # RICH_V1_VIDEO_ACQUISITION_V6_2
        # ====================================================


        # ====================================================
        # RICH_V1_MOVIE_MEDIA_BRIDGE_V6_3
        # ====================================================
        #
        # Famous-movie commentary uses the dedicated,
        # rights-aware MovieMediaResolver.
        #
        # Exact beat identity is retained in evidence.
        # Resolved assets are inserted into the existing media
        # structures so the proven V6.1 matcher/renderer can
        # continue downstream.
        #
        # Non-movie formats remain unchanged.

        v63_movie_media_evidence = {
            "status": "not_applicable",
            "movie_title": "",
            "resolved_beats": 0,
            "video_assets": 0,
            "image_assets": 0,
            "unresolved_beats": 0,
            "beats": [],
        }

        if is_movie_commentary:

            resolved_movie_beats = (
                await self.movie_media_resolver.resolve(
                    beats=visual_beats,
                    content_id=str(content_id),
                    movie_title=movie_title,
                )
            )

            if (
                len(resolved_movie_beats)
                != len(visual_beats)
            ):
                raise RuntimeError(
                    "V6.3 movie resolver returned "
                    "beat coverage mismatch."
                )

            movie_video_assets = []
            movie_image_assets = []

            for beat_index, resolved in enumerate(
                resolved_movie_beats
            ):

                asset = resolved.asset

                row = resolved.to_dict()
                row["beat_index"] = (
                    beat_index + 1
                )

                v63_movie_media_evidence[
                    "beats"
                ].append(row)

                if asset is None:
                    continue

                asset_type = str(
                    getattr(
                        asset,
                        "asset_type",
                        "",
                    )
                ).strip().lower()

                if asset_type == "video":
                    movie_video_assets.append(
                        (
                            beat_index,
                            asset,
                        )
                    )

                elif asset_type == "image":
                    movie_image_assets.append(
                        (
                            beat_index,
                            asset,
                        )
                    )

            # ------------------------------------------------
            # Inject authorized movie assets into the existing
            # scene groups without deleting proven fallbacks.
            #
            # Scene groups and visual beats can have different
            # counts, so mapping is deterministic modulo scene
            # count while the exact beat mapping remains in
            # v63_movie_media_evidence.
            # ------------------------------------------------

            if media_groups:

                for beat_index, asset in (
                    movie_video_assets
                    + movie_image_assets
                ):

                    target_group = (
                        beat_index
                        % len(media_groups)
                    )

                    identity = (
                        self._master_asset_identity(
                            asset
                        )
                    )

                    existing = {
                        self._master_asset_identity(
                            item
                        )
                        for item
                        in media_groups[
                            target_group
                        ]
                    }

                    if (
                        identity
                        and identity
                        not in existing
                    ):
                        media_groups[
                            target_group
                        ].insert(
                            0,
                            asset,
                        )

            # ------------------------------------------------
            # For exact beat-level image fallback, replace the
            # generic beat image only where MovieMediaResolver
            # returned an authorized image for that same beat.
            # ------------------------------------------------

            for beat_index, asset in (
                movie_image_assets
            ):

                if (
                    0
                    <= beat_index
                    < len(beat_render_assets)
                ):
                    beat_render_assets[
                        beat_index
                    ] = asset

            resolved_count = (
                len(movie_video_assets)
                + len(movie_image_assets)
            )

            unresolved_count = (
                len(visual_beats)
                - resolved_count
            )

            v63_movie_media_evidence.update(
                {
                    "status": (
                        "resolved"
                        if resolved_count > 0
                        else
                        "no_authorized_movie_media"
                    ),
                    "movie_title": movie_title,
                    "resolved_beats": (
                        resolved_count
                    ),
                    "video_assets": len(
                        movie_video_assets
                    ),
                    "image_assets": len(
                        movie_image_assets
                    ),
                    "unresolved_beats": (
                        unresolved_count
                    ),
                }
            )


        trend_content_format = trend.get("content_format", {})
        if not isinstance(trend_content_format, dict):
            trend_content_format = {}
        v62_format_name = str(
            trend_content_format.get("format_name", "")
            or genre
            or trend.get("format_name", "")
            or trend.get("format", "")
            or ""
        ).strip()

        if is_movie_commentary:
            v62_source_result = {
                "status": "skipped_for_movie_commentary",
                "reason": "dedicated_movie_media_resolver",
                "assets": [],
                "asset_count": 0,
            }
        else:
            v62_source_result = (
                await self._v62_acquire_source_footage(
                    format_name=v62_format_name,
                    topic=str(topic),
                    content_id=str(content_id),
                )
            )

        v62_source_assets = list(
            v62_source_result.pop(
                "assets",
                [],
            )
        )

        if v62_source_assets and media_groups:
            existing_video_ids = {
                self._master_asset_identity(asset)
                for group in media_groups
                for asset in group
                if getattr(
                    asset,
                    "asset_type",
                    "",
                ) == "video"
            }

            group_count = len(media_groups)

            for asset_index, asset in enumerate(
                v62_source_assets
            ):
                identity = self._master_asset_identity(
                    asset
                )

                if (
                    not identity
                    or identity in existing_video_ids
                ):
                    continue

                target_group = (
                    asset_index
                    % group_count
                )

                media_groups[
                    target_group
                ].append(
                    asset
                )

                existing_video_ids.add(
                    identity
                )

        v62_source_result[
            "injected_video_assets"
        ] = sum(
            1
            for group in media_groups
            for asset in group
            if getattr(
                asset,
                "asset_type",
                "",
            ) == "video"
        )

        v61_video_result = (
            self._v61_build_video_matches(
                media_groups=media_groups,
                visual_beats=visual_beats,
                content_id=str(
                    content_id
                ),
            )
        )

        v61_video_matches = list(
            v61_video_result.get(
                "matches",
                [],
            )
        )

        package = await self.package_builder.build(
            content=generated,
            scenes=storyboard,
            images=render_assets,
            trend=trend,
        )

        ####################################################
        # 9. Render
        ####################################################

        # BLOCK5_VISUAL_QA_BEGIN
        #
        # The previous Stage2B implementation could legally
        # resolve many semantic beats to the same authorized
        # fallback image. That produced a technically valid
        # 12-cut video which visually behaved like a slideshow.
        #
        # Rights authorization has already happened upstream.
        # This gate does not authorize media and does not weaken
        # any rights/evidence requirement. It only evaluates the
        # final authorized beat sequence before expensive render.

        def _block5_asset_identity(asset):
            return media_provenance_identity(asset)

        block5_identities = [
            _block5_asset_identity(asset)
            for asset in beat_render_assets
        ]

        if (
            not block5_identities
            or len(block5_identities)
            != len(visual_beat_dicts)
        ):
            raise RuntimeError(
                "Visual QA rejected semantic sequence: "
                "beat/image coverage mismatch."
            )

        block5_counts = {}

        for identity in block5_identities:
            if not identity:
                raise RuntimeError(
                    "Visual QA rejected semantic sequence: "
                    "unidentifiable authorized asset."
                )

            block5_counts[identity] = (
                block5_counts.get(identity, 0)
                + 1
            )

        block5_distinct_assets = len(
            block5_counts
        )

        block5_largest_share = (
            max(block5_counts.values())
            / len(block5_identities)
        )

        block5_max_repeat_run = 1
        block5_current_repeat_run = 1

        for block5_index in range(
            1,
            len(block5_identities),
        ):
            if (
                block5_identities[block5_index]
                == block5_identities[
                    block5_index - 1
                ]
            ):
                block5_current_repeat_run += 1
                block5_max_repeat_run = max(
                    block5_max_repeat_run,
                    block5_current_repeat_run,
                )
            else:
                block5_current_repeat_run = 1

        block5_minimum_distinct = min(
            4,
            len(block5_identities),
        )

        if (
            block5_distinct_assets
            < block5_minimum_distinct
        ):
            raise RuntimeError(
                "Visual diversity gate rejected sequence: "
                f"{block5_distinct_assets} distinct assets "
                f"for {len(block5_identities)} beats; "
                f"minimum is {block5_minimum_distinct}."
            )

        if block5_max_repeat_run > 2:
            raise RuntimeError(
                "Visual diversity gate rejected sequence: "
                f"same asset appears for "
                f"{block5_max_repeat_run} consecutive beats; "
                "maximum is 2."
            )

        if (
            len(block5_identities) >= 8
            and block5_largest_share > 0.42
        ):
            raise RuntimeError(
                "Visual diversity gate rejected sequence: "
                "one asset occupies "
                f"{block5_largest_share:.0%} of semantic beats; "
                "maximum is 42%."
            )

        block5_visual_metrics = {
            "distinct_assets": (
                block5_distinct_assets
            ),
            "total_beats": (
                len(block5_identities)
            ),
            "largest_asset_share": round(
                block5_largest_share,
                4,
            ),
            "max_consecutive_identical": (
                block5_max_repeat_run
            ),
            "quality_gate": "passed",
        }

        # BLOCK5_VISUAL_QA_END

        video = await self.renderer.render(
            content=generated,
            scenes=storyboard,
            images=render_assets,
            production_package=package,
            visual_beats=visual_beat_dicts,
            beat_images=beat_render_assets,
            beat_videos=v61_video_matches,
        )

        ####################################################
        # 10. Return production evidence
        ####################################################

        return {
            "generated": generated,
            "content_validation": validation,
            "storyboard": storyboard,
            "licensed_media": [
                [
                    {
                        "asset_id": asset.asset_id,
                        "asset_type": asset.asset_type,
                        "file_path": asset.file_path,
                        "source_url": asset.source_url,
                        "source_name": asset.source_name,
                        "creator": asset.creator,
                        "license_name": asset.license_name,
                        "license_url": asset.license_url,
                        "attribution_required": (
                            asset.attribution_required
                        ),
                        "commercial_use_allowed": (
                            asset.commercial_use_allowed
                        ),
                        "relevance_score": (
                            asset.relevance_score
                        ),
                        "content_id": asset.content_id,
                    }
                    for asset in group
                ]
                for group in media_groups
            ],
            "production_package": package,
            "visual_beats": visual_beat_dicts,
            "beat_media": beat_media_evidence,
            "v6_movie_media": v63_movie_media_evidence,
            "v6_video_acquisition": v62_source_result,
            "v6_video_matching": v61_video_result,
            "semantic_media_metrics": {
                "enrichment_budget": self.MAX_SEMANTIC_MEDIA_ENRICHMENTS,
                "enrichment_attempts": semantic_enrichment_attempts,
                "enrichment_successes": semantic_enrichment_successes,
                "fallback_count": semantic_fallback_count,
                "total_beats": len(visual_beats),
                "visual_quality": block5_visual_metrics,
            },
            "video": video,
            "status": "success",
        }







