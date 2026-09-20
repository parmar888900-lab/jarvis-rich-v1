"""YouTube discovery provider for Jarvis Rich V1."""

from __future__ import annotations

from dataclasses import asdict, dataclass

import requests

from backend.config import settings


@dataclass(slots=True)
class YouTubeDiscoveryCandidate:
    video_id: str
    title: str
    description: str
    channel_title: str
    channel_id: str
    published_at: str

    watch_url: str
    thumbnail_url: str

    duration_iso: str
    definition: str

    views: int
    likes: int

    relevance_score: float
    authority_score: float
    quality_score: float
    final_score: float

    source_name: str = "YouTube"

    def to_dict(self) -> dict:
        return asdict(self)


class YouTubeDiscoveryProvider:
    """
    Discover topic-specific YouTube videos.

    This provider performs discovery/metadata analysis only.
    It does not download or rip YouTube media.
    """

    SEARCH_URL = (
        "https://www.googleapis.com/"
        "youtube/v3/search"
    )

    VIDEOS_URL = (
        "https://www.googleapis.com/"
        "youtube/v3/videos"
    )

    OFFICIAL_TERMS = {
        "official",
        "nasa",
        "boeing",
        "airbus",
        "rolex",
        "ferrari",
        "porsche",
        "microsoft",
        "apple",
        "nvidia",
        "national geographic",
        "smithsonian",
        "bbc",
        "discovery",
        "warner bros",
        "universal pictures",
        "paramount pictures",
        "marvel entertainment",
        "sony pictures",
    }

    LOW_VALUE_TERMS = {
        "reaction",
        "fan edit",
        "compilation",
        "reupload",
        "re-upload",
        "shorts compilation",
    }

    def __init__(
        self,
        *,
        api_key: str | None = None,
    ) -> None:

        self.api_key = (
            api_key
            if api_key is not None
            else settings.youtube_api_key
        ).strip()

    @property
    def configured(
        self,
    ) -> bool:

        return bool(
            self.api_key
        )

    def search(
        self,
        *,
        query: str,
        limit: int = 12,
    ) -> list[YouTubeDiscoveryCandidate]:

        if not self.configured:
            raise RuntimeError(
                "YouTube discovery requires "
                "YOUTUBE_API_KEY."
            )

        clean_query = " ".join(
            str(query).split()
        ).strip()

        if not clean_query:
            return []

        ####################################################
        # 1. Search IDs
        ####################################################

        response = requests.get(
            self.SEARCH_URL,
            params={
                "part": "snippet",
                "q": clean_query,
                "type": "video",
                "maxResults": min(
                    max(
                        limit * 2,
                        10,
                    ),
                    50,
                ),
                "order": "relevance",
                "videoEmbeddable": "true",
                "key": self.api_key,
            },
            timeout=25,
        )

        response.raise_for_status()

        search_data = (
            response.json()
        )

        rows = search_data.get(
            "items",
            [],
        )

        video_ids = [
            str(
                row.get(
                    "id",
                    {},
                ).get(
                    "videoId",
                    "",
                )
            )
            for row in rows
        ]

        video_ids = [
            value
            for value in video_ids
            if value
        ]

        if not video_ids:
            return []

        ####################################################
        # 2. Fetch full video metadata/stats
        ####################################################

        metadata_response = requests.get(
            self.VIDEOS_URL,
            params={
                "part": (
                    "snippet,statistics,"
                    "contentDetails"
                ),
                "id": ",".join(
                    video_ids
                ),
                "key": self.api_key,
            },
            timeout=25,
        )

        metadata_response.raise_for_status()

        metadata_rows = (
            metadata_response.json()
            .get(
                "items",
                [],
            )
        )

        output = []

        for row in metadata_rows:

            snippet = row.get(
                "snippet",
                {},
            )

            statistics = row.get(
                "statistics",
                {},
            )

            content_details = row.get(
                "contentDetails",
                {},
            )

            video_id = str(
                row.get(
                    "id",
                    "",
                )
            )

            if not video_id:
                continue

            title = str(
                snippet.get(
                    "title",
                    "",
                )
            )

            description = str(
                snippet.get(
                    "description",
                    "",
                )
            )

            channel_title = str(
                snippet.get(
                    "channelTitle",
                    "",
                )
            )

            thumbnails = snippet.get(
                "thumbnails",
                {},
            )

            thumbnail_url = ""

            for size_name in (
                "maxres",
                "standard",
                "high",
                "medium",
                "default",
            ):

                candidate = thumbnails.get(
                    size_name,
                    {},
                ).get(
                    "url",
                    "",
                )

                if candidate:
                    thumbnail_url = candidate
                    break

            views = self._int_value(
                statistics.get(
                    "viewCount",
                    0,
                )
            )

            likes = self._int_value(
                statistics.get(
                    "likeCount",
                    0,
                )
            )

            relevance = (
                self._relevance_score(
                    query=clean_query,
                    title=title,
                    description=description,
                )
            )

            authority = (
                self._authority_score(
                    title=title,
                    channel_title=channel_title,
                )
            )

            quality = (
                self._quality_score(
                    definition=str(
                        content_details.get(
                            "definition",
                            "",
                        )
                    ),
                    views=views,
                )
            )

            final_score = round(
                relevance * 0.50
                + authority * 0.30
                + quality * 0.20,
                2,
            )

            output.append(
                YouTubeDiscoveryCandidate(
                    video_id=video_id,
                    title=title,
                    description=description,
                    channel_title=(
                        channel_title
                    ),
                    channel_id=str(
                        snippet.get(
                            "channelId",
                            "",
                        )
                    ),
                    published_at=str(
                        snippet.get(
                            "publishedAt",
                            "",
                        )
                    ),
                    watch_url=(
                        "https://www.youtube.com/"
                        f"watch?v={video_id}"
                    ),
                    thumbnail_url=(
                        thumbnail_url
                    ),
                    duration_iso=str(
                        content_details.get(
                            "duration",
                            "",
                        )
                    ),
                    definition=str(
                        content_details.get(
                            "definition",
                            "",
                        )
                    ),
                    views=views,
                    likes=likes,
                    relevance_score=(
                        relevance
                    ),
                    authority_score=(
                        authority
                    ),
                    quality_score=(
                        quality
                    ),
                    final_score=(
                        final_score
                    ),
                )
            )

        output.sort(
            key=lambda item: (
                item.final_score,
                item.authority_score,
                item.views,
            ),
            reverse=True,
        )

        return output[:limit]

    @classmethod
    def _authority_score(
        cls,
        *,
        title: str,
        channel_title: str,
    ) -> float:

        channel = " ".join(
            str(
                channel_title
            ).lower().split()
        )

        title_lower = (
            str(title).lower()
        )

        score = 35.0

        ####################################################
        # Authority must come primarily from the CHANNEL,
        # not from a brand name appearing in the title.
        ####################################################

        exact_high_authority = {
            "rolex",
            "nasa",
            "boeing",
            "airbus",
            "apple",
            "nvidia",
            "microsoft",
            "ferrari",
            "porsche",
            "marvel entertainment",
            "warner bros. pictures",
            "warner bros. entertainment",
            "universal pictures",
            "paramount pictures",
            "sony pictures entertainment",
            "national geographic",
            "smithsonian channel",
        }

        if channel in exact_high_authority:
            score = 100.0

        elif any(
            term == channel
            for term in cls.OFFICIAL_TERMS
        ):
            score = 95.0

        ####################################################
        # Explicit official-channel naming helps, but does
        # not automatically equal first-party authority.
        ####################################################

        elif (
            "official" in channel
            or channel.endswith(
                " official"
            )
        ):
            score = 80.0

        ####################################################
        # Established specialist channels still have some
        # source value, but remain below first-party media.
        ####################################################

        elif any(
            term in channel
            for term in (
                "watchfinder",
                "crown & caliber",
                "bob's watches",
                "wristcheck",
                "hodinkee",
                "watchbox",
            )
        ):
            score = 65.0

        ####################################################
        # Penalize low-value derivative/reaction content.
        ####################################################

        combined = (
            channel
            + " "
            + title_lower
        )

        if any(
            term in combined
            for term in cls.LOW_VALUE_TERMS
        ):
            score -= 30.0

        return round(
            max(
                0.0,
                min(
                    score,
                    100.0,
                ),
            ),
            2,
        )

    @staticmethod
    def _relevance_score(
        *,
        query: str,
        title: str,
        description: str,
    ) -> float:

        query_words = {
            word
            for word in (
                query.lower().split()
            )
            if len(word) >= 3
        }

        title_words = set(
            title.lower().split()
        )

        body_words = set(
            description.lower().split()
        )

        if not query_words:
            return 0.0

        title_overlap = len(
            query_words
            .intersection(
                title_words
            )
        )

        body_overlap = len(
            query_words
            .intersection(
                body_words
            )
        )

        title_ratio = (
            title_overlap
            / len(query_words)
        )

        body_ratio = (
            body_overlap
            / len(query_words)
        )

        score = (
            title_ratio * 75.0
            + body_ratio * 25.0
        )

        return round(
            min(
                score,
                100.0,
            ),
            2,
        )

    @staticmethod
    def _quality_score(
        *,
        definition: str,
        views: int,
    ) -> float:

        score = 45.0

        if (
            definition
            .strip()
            .lower()
            == "hd"
        ):
            score += 30.0

        if views >= 1_000_000:
            score += 20.0

        elif views >= 100_000:
            score += 12.0

        elif views >= 10_000:
            score += 6.0

        return round(
            min(
                score,
                100.0,
            ),
            2,
        )

    @staticmethod
    def _int_value(
        value,
    ) -> int:

        try:
            return int(
                value
                or 0
            )

        except (
            TypeError,
            ValueError,
        ):
            return 0
