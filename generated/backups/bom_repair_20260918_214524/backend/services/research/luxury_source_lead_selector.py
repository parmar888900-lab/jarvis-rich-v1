"""High-quality source lead selection for Rich V1 luxury videos."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from backend.services.research.providers.youtube import (
    YouTubeDiscoveryProvider,
)
from backend.services.research.youtube_thumbnail_verifier import (
    YouTubeThumbnailVerifier,
)


@dataclass(slots=True)
class LuxurySourceLead:
    video_id: str
    title: str
    channel_title: str
    watch_url: str
    thumbnail_url: str

    authority_score: float
    discovery_score: float
    visual_positive_score: float
    visual_negative_score: float
    visual_margin: float

    final_score: float
    source_type: str

    def to_dict(self) -> dict:
        return asdict(self)


class LuxurySourceLeadSelector:
    """
    Convert broad YouTube discovery results into a small,
    visually verified source-lead pool.

    Discovery only: this does not download YouTube video media.
    """

    MIN_VISUAL_POSITIVE = 0.22
    MIN_VISUAL_MARGIN = 0.025

    def __init__(
        self,
        *,
        youtube_provider=None,
        thumbnail_verifier=None,
    ) -> None:

        self.youtube = (
            youtube_provider
            if youtube_provider is not None
            else YouTubeDiscoveryProvider()
        )

        self.verifier = (
            thumbnail_verifier
            if thumbnail_verifier is not None
            else YouTubeThumbnailVerifier()
        )

    def select(
        self,
        *,
        topic: str,
        limit: int = 12,
    ) -> list[LuxurySourceLead]:

        clean_topic = " ".join(
            str(topic).split()
        ).strip()

        if not clean_topic:
            return []

        queries = self._queries(
            clean_topic
        )

        positive_prompts = [
            f"{clean_topic} product close up",
            f"{clean_topic} luxury product shot",
            f"{clean_topic} macro detail",
            "luxury wristwatch close up",
            "mechanical watch movement",
            "premium watch dial macro photography",
            "luxury product cinematography",
        ]

        negative_prompts = [
            "person talking to camera",
            "podcast interview",
            "presenter sitting at desk",
            "face portrait",
            "text-heavy thumbnail",
            "generic talking-head review",
            "reaction video",
            "fake product comparison",
        ]

        by_video_id: dict[
            str,
            LuxurySourceLead,
        ] = {}

        for query in queries:

            candidates = self.youtube.search(
                query=query,
                limit=8,
            )

            for candidate in candidates:

                verification = (
                    self.verifier.verify(
                        thumbnail_url=(
                            candidate.thumbnail_url
                        ),
                        positive_prompts=(
                            positive_prompts
                        ),
                        negative_prompts=(
                            negative_prompts
                        ),
                    )
                )

                if not verification.valid:
                    continue

                if (
                    verification.positive_score
                    < self.MIN_VISUAL_POSITIVE
                ):
                    continue

                if (
                    verification.margin
                    < self.MIN_VISUAL_MARGIN
                ):
                    continue

                source_type = (
                    self._source_type(
                        candidate.authority_score
                    )
                )

                visual_score = min(
                    100.0,
                    (
                        verification.positive_score
                        * 100.0
                    )
                    + (
                        max(
                            verification.margin,
                            0.0,
                        )
                        * 100.0
                    ),
                )

                final_score = round(
                    candidate.discovery_score
                    if hasattr(
                        candidate,
                        "discovery_score",
                    )
                    else candidate.final_score,
                    2,
                )

                final_score = round(
                    final_score * 0.40
                    + candidate.authority_score * 0.30
                    + visual_score * 0.30,
                    2,
                )

                lead = LuxurySourceLead(
                    video_id=(
                        candidate.video_id
                    ),
                    title=(
                        candidate.title
                    ),
                    channel_title=(
                        candidate.channel_title
                    ),
                    watch_url=(
                        candidate.watch_url
                    ),
                    thumbnail_url=(
                        candidate.thumbnail_url
                    ),
                    authority_score=(
                        candidate.authority_score
                    ),
                    discovery_score=(
                        candidate.final_score
                    ),
                    visual_positive_score=(
                        verification.positive_score
                    ),
                    visual_negative_score=(
                        verification.negative_score
                    ),
                    visual_margin=(
                        verification.margin
                    ),
                    final_score=(
                        final_score
                    ),
                    source_type=(
                        source_type
                    ),
                )

                previous = by_video_id.get(
                    lead.video_id
                )

                if (
                    previous is None
                    or lead.final_score
                    > previous.final_score
                ):
                    by_video_id[
                        lead.video_id
                    ] = lead

        output = list(
            by_video_id.values()
        )

        output.sort(
            key=lambda item: (
                item.final_score,
                item.authority_score,
                item.visual_margin,
            ),
            reverse=True,
        )

        return output[:limit]

    @staticmethod
    def _queries(
        topic: str,
    ) -> list[str]:

        return [
            f"{topic} official",
            f"{topic} cinematic",
            f"{topic} close up",
            f"{topic} macro",
            f"{topic} movement",
            f"{topic} craftsmanship",
        ]

    @staticmethod
    def _source_type(
        authority_score: float,
    ) -> str:

        if authority_score >= 95.0:
            return "first_party"

        if authority_score >= 60.0:
            return "established_specialist"

        return "third_party"
