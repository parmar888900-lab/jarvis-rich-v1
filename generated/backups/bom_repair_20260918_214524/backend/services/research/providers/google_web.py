"""Google web discovery for Jarvis Rich V1."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from urllib.parse import urlparse

import requests

from backend.config import settings


@dataclass(slots=True)
class GoogleWebCandidate:
    title: str
    url: str
    snippet: str

    domain: str

    authority_score: float
    relevance_score: float
    final_score: float

    source_name: str = "Google"

    def to_dict(self) -> dict:
        return asdict(self)


class GoogleDiscoveryProvider:
    """
    Discover official/source web pages for Rich V1 media acquisition.

    This provider discovers source pages only.
    It does not assume that media found on a page may be reused.
    """

    SEARCH_URL = (
        "https://www.googleapis.com/"
        "customsearch/v1"
    )

    HIGH_AUTHORITY_DOMAINS = {
        "rolex.com",
        "nasa.gov",
        "boeing.com",
        "airbus.com",
        "apple.com",
        "nvidia.com",
        "ferrari.com",
        "porsche.com",
        "marvel.com",
        "warnerbros.com",
        "sony.com",
        "paramount.com",
    }

    SOURCE_TERMS = {
        "media",
        "press",
        "newsroom",
        "gallery",
        "download",
        "assets",
        "images",
        "video",
        "product",
        "official",
    }

    LOW_VALUE_TERMS = {
        "reddit",
        "pinterest",
        "facebook",
        "tiktok",
        "forum",
        "reaction",
        "review",
    }

    def __init__(
        self,
        *,
        api_key: str | None = None,
        cx: str | None = None,
    ) -> None:

        self.api_key = (
            api_key
            if api_key is not None
            else settings.google_search_api_key
        ).strip()

        self.cx = (
            cx
            if cx is not None
            else settings.google_search_cx
        ).strip()

    @property
    def configured(
        self,
    ) -> bool:

        return bool(
            self.api_key
            and self.cx
        )

    def search(
        self,
        *,
        query: str,
        limit: int = 10,
    ) -> list[GoogleWebCandidate]:

        if not self.configured:

            raise RuntimeError(
                "Google discovery requires "
                "GOOGLE_SEARCH_API_KEY and "
                "GOOGLE_SEARCH_CX."
            )

        clean_query = " ".join(
            str(query).split()
        ).strip()

        if not clean_query:
            return []

        response = requests.get(
            self.SEARCH_URL,
            params={
                "key": self.api_key,
                "cx": self.cx,
                "q": clean_query,
                "num": min(
                    max(
                        limit,
                        1,
                    ),
                    10,
                ),
            },
            timeout=25,
        )

        response.raise_for_status()

        data = response.json()

        output = []

        for item in data.get(
            "items",
            [],
        ):

            title = str(
                item.get(
                    "title",
                    "",
                )
            )

            url = str(
                item.get(
                    "link",
                    "",
                )
            )

            snippet = str(
                item.get(
                    "snippet",
                    "",
                )
            )

            domain = (
                urlparse(
                    url
                )
                .netloc
                .lower()
            )

            if domain.startswith(
                "www."
            ):
                domain = domain[4:]

            authority = (
                self._authority_score(
                    domain=domain,
                    title=title,
                    snippet=snippet,
                )
            )

            relevance = (
                self._relevance_score(
                    query=clean_query,
                    title=title,
                    snippet=snippet,
                )
            )

            final_score = round(
                authority * 0.55
                + relevance * 0.45,
                2,
            )

            output.append(
                GoogleWebCandidate(
                    title=title,
                    url=url,
                    snippet=snippet,
                    domain=domain,
                    authority_score=(
                        authority
                    ),
                    relevance_score=(
                        relevance
                    ),
                    final_score=(
                        final_score
                    ),
                )
            )

        output.sort(
            key=lambda row: (
                row.final_score,
                row.authority_score,
            ),
            reverse=True,
        )

        return output[:limit]

    @classmethod
    def _authority_score(
        cls,
        *,
        domain: str,
        title: str,
        snippet: str,
    ) -> float:

        score = 35.0

        if domain in cls.HIGH_AUTHORITY_DOMAINS:
            score = 100.0

        elif any(
            domain.endswith(
                "." + authority_domain
            )
            for authority_domain
            in cls.HIGH_AUTHORITY_DOMAINS
        ):
            score = 95.0

        combined = (
            f"{title} {snippet}"
            .lower()
        )

        if any(
            term in combined
            for term in cls.SOURCE_TERMS
        ):
            score += 10.0

        if any(
            term in domain
            or term in combined
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
        snippet: str,
    ) -> float:

        query_words = {
            word
            for word in query.lower().split()
            if len(word) >= 3
        }

        if not query_words:
            return 0.0

        title_words = set(
            title.lower().split()
        )

        snippet_words = set(
            snippet.lower().split()
        )

        title_overlap = len(
            query_words.intersection(
                title_words
            )
        )

        snippet_overlap = len(
            query_words.intersection(
                snippet_words
            )
        )

        score = (
            (
                title_overlap
                / len(query_words)
            )
            * 70.0
            +
            (
                snippet_overlap
                / len(query_words)
            )
            * 30.0
        )

        return round(
            min(
                score,
                100.0,
            ),
            2,
        )
