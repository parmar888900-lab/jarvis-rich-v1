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

from backend.services.content_generator import ContentGenerator
from backend.services.content_validator import ContentValidator
from backend.services.intelligence.content_format_classifier import ContentFormatClassifier
from backend.services.intelligence.movie_topic_parser import MovieTopicParser
from backend.services.research.evergreen_research_service import EvergreenResearchService
from backend.services.research.movie_research_service import MovieResearchService
from backend.services.storyboard.generator import StoryboardGenerator
from backend.services.video.asset_collector import AssetCollector
from backend.services.video.media_query_builder import MediaQueryBuilder
from backend.services.video.media_sources.wikimedia import (
    WikimediaCommonsProvider,
)
from backend.services.video.production_package import (
    ProductionPackageBuilder,
)
from backend.services.video.visual_beat_planner import VisualBeatPlanner
from backend.services.video_renderer.renderer import VideoRenderer


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
    @classmethod
    def _master_query_variants(
        cls,
        *,
        topic: str,
        beat,
    ) -> list[str]:
        """
        SEMANTIC_VISUAL_V4

        Build literal, mechanism-specific media searches instead
        of broad social-media / generic recording-room searches.
        """

        search_query = str(
            getattr(beat, "search_query", "") or ""
        ).strip()

        visual_requirement = str(
            getattr(beat, "visual_requirement", "") or ""
        ).strip()

        purpose = str(
            getattr(beat, "purpose", "") or ""
        ).strip()

        combined = " ".join(
            (
                str(topic),
                search_query,
                visual_requirement,
                purpose,
            )
        ).lower()

        raw = []

        # Exact beat requirement remains first.
        if visual_requirement:
            raw.append(visual_requirement)

        if search_query:
            raw.append(search_query)

        # Domain-specific literal expansions.
        if any(
            token in combined
            for token in (
                "sound effect",
                "sound effects",
                "foley",
                "recorded separately",
                "footstep",
                "footsteps",
            )
        ):
            if any(
                token in combined
                for token in (
                    "foot",
                    "step",
                    "walk",
                    "shoe",
                )
            ):
                raw.extend(
                    [
                        "Foley artist recording footsteps studio",
                        "Foley footsteps sound effects recording",
                        "film Foley artist shoes footsteps",
                    ]
                )

            elif any(
                token in combined
                for token in (
                    "prop",
                    "object",
                    "door",
                    "cloth",
                    "fabric",
                    "glass",
                    "metal",
                )
            ):
                raw.extend(
                    [
                        "Foley artist movie props sound effects",
                        "Foley studio props film sound recording",
                        "film sound effects Foley props",
                    ]
                )

            elif any(
                token in combined
                for token in (
                    "edit",
                    "post",
                    "mix",
                    "timeline",
                    "sync",
                )
            ):
                raw.extend(
                    [
                        "film sound editor post production studio",
                        "movie sound design editing workstation",
                        "film audio post production sound editor",
                    ]
                )

            elif any(
                token in combined
                for token in (
                    "microphone",
                    "record",
                    "studio",
                )
            ):
                raw.extend(
                    [
                        "Foley artist recording sound effects studio",
                        "film Foley recording studio microphone",
                        "movie sound effects recording Foley artist",
                    ]
                )

            else:
                raw.extend(
                    [
                        "Foley artist recording movie sound effects",
                        "film Foley studio sound effects",
                        "movie sound design Foley recording",
                    ]
                )

        # Keep the topic as context only after literal searches.
        if search_query and topic:
            raw.append(
                f"{search_query} {topic}"
            )

        output = []
        seen = set()

        for query in raw:
            clean = " ".join(
                str(query).split()
            ).strip()

            if not clean:
                continue

            key = clean.casefold()

            if key in seen:
                continue

            seen.add(key)
            output.append(clean)

        # Two provider requests maximum per beat.
        return output[:2]


    @classmethod
    @classmethod
    def _master_metadata_score(
        cls,
        *,
        asset,
        query: str,
        topic: str,
    ) -> float:
        """
        SEMANTIC_VISUAL_V4

        Weight the literal beat query more strongly than the broad
        topic and require metadata evidence when available.
        """

        query_tokens = cls._master_query_tokens(query)
        topic_tokens = cls._master_query_tokens(topic)

        fields = []

        for attribute in (
            "title",
            "description",
            "source_url",
            "asset_id",
            "local_path",
        ):
            value = getattr(
                asset,
                attribute,
                None,
            )

            if value:
                fields.append(str(value))

        metadata = " ".join(fields)

        available = cls._master_query_tokens(
            metadata
        )

        if not available:
            return 0.0

        query_overlap = len(
            query_tokens.intersection(
                available
            )
        )

        topic_overlap = len(
            topic_tokens.intersection(
                available
            )
        )

        query_denominator = max(
            1,
            min(len(query_tokens), 6),
        )

        topic_denominator = max(
            1,
            min(len(topic_tokens), 6),
        )

        query_score = (
            query_overlap
            / query_denominator
        )

        topic_score = (
            topic_overlap
            / topic_denominator
        )

        # Literal beat relevance dominates broad topic relevance.
        score = (
            query_score * 0.78
            + topic_score * 0.22
        )

        return min(
            1.0,
            max(0.0, score),
        )


    @classmethod
    @classmethod
    def _master_choose_asset(
        cls,
        *,
        candidates,
        query: str,
        topic: str,
        used_identities: set[str],
        previous_identity: str,
    ):
        """
        SEMANTIC_VISUAL_V4

        Reject weak generic candidates rather than allowing
        diversity alone to make them eligible.
        """

        ranked = []

        domain_tokens = {
            "foley",
            "film",
            "sound",
            "audio",
            "studio",
            "recording",
            "editor",
            "production",
            "effects",
            "footsteps",
            "microphone",
            "cinema",
        }

        negative_tokens = {
            "selfie",
            "influencer",
            "webcam",
            "vlog",
            "blogger",
            "portrait",
            "fashion",
            "makeup",
            "ringlight",
            "ring-light",
            "livestream",
            "streamer",
        }

        for asset in candidates:
            if getattr(asset, "asset_type", "") != "image":
                continue

            identity = cls._master_asset_identity(asset)

            if not identity:
                continue

            fields = []

            for attribute in (
                "title",
                "description",
                "source_url",
                "asset_id",
                "local_path",
            ):
                value = getattr(
                    asset,
                    attribute,
                    None,
                )

                if value:
                    fields.append(str(value))

            metadata_text = " ".join(fields).lower()

            semantic_score = cls._master_metadata_score(
                asset=asset,
                query=query,
                topic=topic,
            )

            metadata_tokens = cls._master_query_tokens(
                metadata_text
            )

            domain_overlap = len(
                metadata_tokens.intersection(
                    domain_tokens
                )
            )

            negative_overlap = sum(
                1
                for token in negative_tokens
                if token in metadata_text
            )

            unused_bonus = (
                0.40
                if identity not in used_identities
                else 0.0
            )

            domain_bonus = min(
                0.30,
                domain_overlap * 0.10,
            )

            generic_penalty = min(
                0.75,
                negative_overlap * 0.25,
            )

            consecutive_penalty = (
                1.25
                if identity == previous_identity
                else 0.0
            )

            final_score = (
                semantic_score
                + unused_bonus
                + domain_bonus
                - generic_penalty
                - consecutive_penalty
            )

            ranked.append(
                (
                    final_score,
                    semantic_score,
                    domain_overlap,
                    negative_overlap,
                    identity,
                    asset,
                )
            )

        if not ranked:
            return None

        ranked.sort(
            key=lambda row: (
                row[0],
                row[1],
                row[2],
            ),
            reverse=True,
        )

        # Preferred: unused + non-consecutive + literal relevance.
        for (
            _,
            semantic_score,
            domain_overlap,
            negative_overlap,
            identity,
            asset,
        ) in ranked:
            if (
                identity != previous_identity
                and identity not in used_identities
                and negative_overlap == 0
                and semantic_score >= 0.28
                and domain_overlap >= 1
            ):
                return asset

        # Second tier: still require semantic evidence.
        for (
            _,
            semantic_score,
            domain_overlap,
            negative_overlap,
            identity,
            asset,
        ) in ranked:
            if (
                identity != previous_identity
                and negative_overlap == 0
                and semantic_score >= 0.34
            ):
                return asset

        # Fail closed here. Stage fallback logic can decide whether
        # an already-authorized fallback is acceptable.
        return None


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

        visual_beats = self.visual_beat_planner.plan(
            content=generated,
            topic=topic,
            genre=genre,
            format_name=(
                format_decision.format_name
            ),
        )

        if not visual_beats:
            raise RuntimeError(
                "VisualBeatPlanner produced no visual beats."
            )

        visual_beat_dicts = (
            self.visual_beat_planner.to_dicts(
                visual_beats
            )
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
            if asset is None:
                return ""

            for attribute in (
                "image_path",
                "file_path",
                "local_path",
                "path",
                "source_url",
                "asset_id",
            ):
                value = getattr(
                    asset,
                    attribute,
                    None,
                )

                if value:
                    return str(value).strip().lower()

            if isinstance(asset, dict):
                for key in (
                    "image_path",
                    "file_path",
                    "local_path",
                    "path",
                    "source_url",
                    "asset_id",
                ):
                    value = asset.get(key)

                    if value:
                        return str(value).strip().lower()

            return str(asset).strip().lower()

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









