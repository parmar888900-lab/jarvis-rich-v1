"""Targeted visual-beat recovery for Jarvis Rich V1."""

from __future__ import annotations

from dataclasses import dataclass, field

from backend.services.video.media_asset import MediaAsset
from backend.services.video.source_clip_indexer import (
    SourceClipIndexer,
    IndexedSourceClip,
)
from backend.services.video.strict_clip_matcher import (
    StrictClipMatcher,
    StrictMatchedClip,
)
from backend.services.video.visual_identity_verifier import (
    VisualIdentityVerifier,
)
from backend.services.video.visual_beat_source_planner import (
    SourceVisualBeat,
)
from backend.services.video.media_sources.internet_archive import (
    InternetArchiveProvider,
)
from backend.services.video.media_sources.wikimedia import (
    WikimediaCommonsProvider,
)


@dataclass(slots=True)
class BeatResolutionResult:
    beat_id: str
    status: str

    match: StrictMatchedClip | None = None

    attempted_queries: list[str] = field(
        default_factory=list
    )

    rejection_reasons: list[str] = field(
        default_factory=list
    )


class TargetedBeatResolver:
    """
    Recover unresolved visual beats by searching specifically for
    that beat, indexing the returned footage, matching clips, then
    applying hard visual-identity verification.
    """

    RESULTS_PER_QUERY = 2
    MAX_QUERIES = 3

    def __init__(
        self,
        *,
        providers=None,
        indexer=None,
        matcher=None,
        verifier=None,
    ) -> None:

        self.providers = (
            providers
            if providers is not None
            else [
                WikimediaCommonsProvider(),
                InternetArchiveProvider(),
            ]
        )

        self.indexer = (
            indexer
            if indexer is not None
            else SourceClipIndexer()
        )

        self.matcher = (
            matcher
            if matcher is not None
            else StrictClipMatcher()
        )

        self.verifier = (
            verifier
            if verifier is not None
            else VisualIdentityVerifier()
        )

    async def resolve(
        self,
        *,
        beat: SourceVisualBeat,
        content_id: str,
    ) -> BeatResolutionResult:

        attempted_queries = []
        rejection_reasons = []

        for query_index, query in enumerate(
            beat.search_queries[
                :self.MAX_QUERIES
            ],
            start=1,
        ):

            attempted_queries.append(
                query
            )

            assets: list[
                MediaAsset
            ] = []

            ################################################
            # Retrieve real subject-specific footage.
            ################################################

            for provider in self.providers:

                try:

                    found = await provider.search_and_download(
                        query=query,
                        content_id=(
                            f"{content_id}-"
                            f"{beat.beat_id}-"
                            f"q{query_index}"
                        ),
                        limit=(
                            self.RESULTS_PER_QUERY
                        ),
                    )

                except Exception as exc:

                    rejection_reasons.append(
                        (
                            f"{provider.__class__.__name__}:"
                            f"provider_error:"
                            f"{type(exc).__name__}"
                        )
                    )

                    continue

                for asset in found:

                    if asset.asset_type != "video":
                        continue

                    if (
                        asset.commercial_use_allowed
                        is not True
                    ):
                        continue

                    assets.append(
                        asset
                    )

            if not assets:
                rejection_reasons.append(
                    f"{query}:no_video_assets"
                )
                continue

            ################################################
            # Index every candidate video into short shots.
            ################################################

            clips: list[
                IndexedSourceClip
            ] = []

            for asset in assets:

                clips.extend(
                    self.indexer.index_asset(
                        asset=asset,
                        content_id=(
                            f"{content_id}-"
                            f"{beat.beat_id}-"
                            f"q{query_index}"
                        ),
                    )
                )

            if not clips:
                rejection_reasons.append(
                    f"{query}:no_indexed_clips"
                )
                continue

            ################################################
            # Rank clips against this exact beat.
            ################################################

            matches = (
                self.matcher.match_many(
                    beats=[
                        beat
                    ],
                    clips=clips,
                    max_reuse_per_source=20,
                )
            )

            if not matches:
                rejection_reasons.append(
                    f"{query}:no_semantic_match"
                )
                continue

            ################################################
            # Do not trust the top CLIP match yet.
            # Hard-check visual identity.
            ################################################

            for match in matches:

                required_prompts = [
                    beat.visual_goal,
                    *beat.search_queries,
                ]

                reject_prompts = [
                    *beat.negative_visuals,
                    "generic unrelated machinery",
                    "unrelated household object",
                    "generic stock footage",
                ]

                verification = (
                    self.verifier.verify(
                        image_path=(
                            match.preview_path
                        ),
                        required_prompts=(
                            required_prompts
                        ),
                        reject_prompts=(
                            reject_prompts
                        ),
                    )
                )

                if verification.valid:

                    return BeatResolutionResult(
                        beat_id=(
                            beat.beat_id
                        ),
                        status="resolved",
                        match=match,
                        attempted_queries=(
                            attempted_queries
                        ),
                        rejection_reasons=(
                            rejection_reasons
                        ),
                    )

                rejection_reasons.append(
                    (
                        f"{query}:"
                        f"{match.clip_id}:"
                        f"{verification.reason}:"
                        f"pos={verification.positive_score}:"
                        f"neg={verification.negative_score}:"
                        f"margin={verification.margin}"
                    )
                )

        ####################################################
        # Fail honestly. Renderer must never fill this beat
        # with an unrelated visual.
        ####################################################

        return BeatResolutionResult(
            beat_id=beat.beat_id,
            status=(
                "required_visual_not_found"
            ),
            match=None,
            attempted_queries=(
                attempted_queries
            ),
            rejection_reasons=(
                rejection_reasons
            ),
        )
