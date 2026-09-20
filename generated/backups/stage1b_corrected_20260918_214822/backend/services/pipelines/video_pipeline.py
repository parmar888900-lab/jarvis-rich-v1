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
from backend.services.video_renderer.renderer import VideoRenderer


class VideoPipeline:

    MIN_ASSETS_PER_SCENE = 1
    TARGET_ASSETS_PER_SCENE = 1

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

        video = await self.renderer.render(
            content=generated,
            scenes=storyboard,
            images=render_assets,
            production_package=package,
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
            "video": video,
            "status": "success",
        }









