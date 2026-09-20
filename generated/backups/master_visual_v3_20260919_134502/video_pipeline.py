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
    MAX_SEMANTIC_MEDIA_ENRICHMENTS = 6

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
                        limit=1,
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

                image_asset = next(
                    (
                        asset
                        for asset in authorized
                        if asset.asset_type
                        == "image"
                    ),
                    None,
                )

                if image_asset is None:
                    continue

                authorized_scene_assets.append(
                    image_asset
                )

                # Current renderer needs only one image
                # per narration scene. Stop immediately.
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

        for beat in visual_beats:

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

            fallback_asset = next(
                (
                    asset
                    for asset in media_groups[stage_index]
                    if asset.asset_type == "image"
                ),
                None,
            )

            if fallback_asset is None:
                raise RuntimeError(
                    "Stage 2B fallback media missing for "
                    f"narration stage {narration_index}."
                )

            selected_asset = fallback_asset
            selected_via = "stage_fallback"

            query = str(
                beat.search_query
            ).strip()

            if query and semantic_enrichment_attempts < self.MAX_SEMANTIC_MEDIA_ENRICHMENTS:

                semantic_enrichment_attempts += 1

                try:

                    found = await (
                        self.media_provider
                        .search_and_download(
                            query=query,
                            content_id=content_id,
                            limit=1,
                        )
                    )

                    if found:

                        try:

                            authorized = (
                                self.asset_collector.authorize(
                                    found,
                                    content_id=content_id,
                                )
                            )

                        except RuntimeError:

                            authorized = []

                        candidate = next(
                            (
                                asset
                                for asset in authorized
                                if asset.asset_type == "image"
                            ),
                            None,
                        )

                        if candidate is not None:

                            selected_asset = candidate
                            selected_via = "semantic_query"
                            semantic_enrichment_successes += 1

                except Exception:

                    # Beat enrichment must never make a valid
                    # production fail. The original authorized
                    # scene asset remains the fallback.
                    selected_asset = fallback_asset
                    selected_via = "stage_fallback"

            if selected_via == "stage_fallback":
                semantic_fallback_count += 1

            beat_render_assets.append(
                selected_asset
            )

            beat_media_evidence.append(
                {
                    "beat_id": beat.beat_id,
                    "narration_index": narration_index,
                    "purpose": beat.purpose,
                    "query": query,
                    "selected_via": selected_via,
                    "asset_id": selected_asset.asset_id,
                    "source_name": selected_asset.source_name,
                    "source_url": selected_asset.source_url,
                    "license_name": selected_asset.license_name,
                    "commercial_use_allowed": (
                        selected_asset.commercial_use_allowed
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









