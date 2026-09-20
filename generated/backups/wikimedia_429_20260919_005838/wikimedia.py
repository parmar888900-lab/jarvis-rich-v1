"""Wikimedia Commons media provider for Jarvis Rich V1."""

from __future__ import annotations

import asyncio
import html
import json
import re
import urllib.parse
import urllib.request
import urllib.error
import time
from pathlib import Path
from uuid import uuid4

from backend.services.runtime.runtime_config import RuntimeConfig
from backend.services.video.media_asset import MediaAsset


class WikimediaCommonsProvider:
    """Find explicitly licensed real media on Wikimedia Commons."""

    API_URL = "https://commons.wikimedia.org/w/api.php"

    USER_AGENT = (
        "Jarvis-Rich-V1/1.0 "
        "(automated licensed-media research)"
    )

    ALLOWED_MIME_TYPES = {
        "image/jpeg",
        "image/png",
        "image/webp",
        "video/webm",
        "video/mp4",
        "video/ogg",
    }

    # Commercial reuse is permitted under these licenses,
    # subject to their attribution/share-alike requirements.
    ALLOWED_LICENSE_MARKERS = {
        "public domain",
        "cc0",
        "cc by ",
        "cc-by-",
        "cc by-sa",
        "cc-by-sa",
    }

    def __init__(
        self,
        runtime_config: RuntimeConfig | None = None,
    ) -> None:

        config = (
            runtime_config
            if runtime_config is not None
            else RuntimeConfig.from_environment()
        )

        self.base_dir = (
            Path(config.generated_dir)
            / "licensed_media"
        )

        self.base_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

    async def search_and_download(
        self,
        *,
        query: str,
        content_id: str,
        limit: int = 3,
    ) -> list[MediaAsset]:

        return await asyncio.to_thread(
            self._search_and_download_sync,
            query,
            content_id,
            limit,
        )

    async def download_exact_file(
        self,
        *,
        file_title: str,
        content_id: str,
    ) -> MediaAsset | None:
        """Download one exact Wikimedia Commons File: title."""

        return await asyncio.to_thread(
            self._download_exact_file_sync,
            file_title,
            content_id,
        )

    def _download_exact_file_sync(
        self,
        file_title: str,
        content_id: str,
    ) -> MediaAsset | None:

        if not file_title.startswith("File:"):
            file_title = "File:" + file_title

        result = self._api(
            {
                "action": "query",
                "titles": file_title,
                "prop": "imageinfo",
                "iiprop": "url|mime|extmetadata",
                "format": "json",
                "formatversion": "2",
            }
        )

        pages = (
            result
            .get("query", {})
            .get("pages", [])
        )

        if not pages:
            return None

        page = pages[0]

        infos = page.get(
            "imageinfo",
            [],
        )

        if not infos:
            return None

        info = infos[0]

        mime = str(
            info.get("mime", "")
        ).lower()

        if mime not in self.ALLOWED_MIME_TYPES:
            return None

        metadata = info.get(
            "extmetadata",
            {},
        )

        license_name = self._meta(
            metadata,
            "LicenseShortName",
        )

        usage_terms = self._meta(
            metadata,
            "UsageTerms",
        )

        license_text = (
            f"{license_name} {usage_terms}"
        ).lower()

        if not self._license_allowed(
            license_text
        ):
            return None

        media_url = str(
            info.get(
                "url",
                "",
            )
        ).strip()

        if not media_url:
            return None

        output_dir = (
            self.base_dir
            / self._safe_name(
                content_id
            )
        )

        output_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        suffix = self._suffix_from_url(
            media_url,
            mime,
        )

        destination = (
            output_dir
            / (
                self._safe_name(
                    file_title
                )[:60]
                + suffix
            )
        )

        try:
            self._download(
                media_url,
                destination,
            )
        except Exception:
            return None

        source_url = str(
            info.get(
                "descriptionurl",
                "",
            )
            or media_url
        ).strip()

        creator = self._clean_html(
            self._meta(
                metadata,
                "Artist",
            )
        )

        license_url = self._meta(
            metadata,
            "LicenseUrl",
        )

        attribution_required = not (
            "public domain"
            in license_text
            or "cc0"
            in license_text
        )

        return MediaAsset(
            asset_id=uuid4().hex,
            asset_type=(
                "video"
                if mime.startswith(
                    "video/"
                )
                else "image"
            ),
            file_path=str(
                destination
            ),
            source_url=source_url,
            source_name=(
                "Wikimedia Commons"
            ),
            creator=creator or None,
            license_name=(
                license_name
                or usage_terms
                or None
            ),
            license_url=(
                license_url or None
            ),
            attribution_required=(
                attribution_required
            ),
            commercial_use_allowed=True,
            relevance_score=100.0,
            content_id=content_id,
        )
    def _search_and_download_sync(
        self,
        query: str,
        content_id: str,
        limit: int,
    ) -> list[MediaAsset]:

        search_results = self._api(
            {
                "action": "query",
                "generator": "search",
                "gsrsearch": query,
                "gsrnamespace": "6",
                "gsrlimit": str(
                    max(limit * 5, 10)
                ),
                "prop": "imageinfo",
                "iiprop": (
                    "url|mime|extmetadata"
                ),
                "iiurlwidth": "1600",
                "format": "json",
                "formatversion": "2",
            }
        )

        pages = (
            search_results
            .get("query", {})
            .get("pages", [])
        )

        output_dir = (
            self.base_dir
            / self._safe_name(content_id)
        )

        output_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        assets: list[MediaAsset] = []

        for rank, page in enumerate(
            pages,
            start=1,
        ):

            if len(assets) >= limit:
                break

            imageinfo = page.get(
                "imageinfo",
                [],
            )

            if not imageinfo:
                continue

            info = imageinfo[0]

            mime = str(
                info.get("mime", "")
            ).lower()

            if mime not in self.ALLOWED_MIME_TYPES:
                continue

            metadata = info.get(
                "extmetadata",
                {},
            )

            license_name = self._meta(
                metadata,
                "LicenseShortName",
            )

            usage_terms = self._meta(
                metadata,
                "UsageTerms",
            )

            license_text = (
                f"{license_name} {usage_terms}"
            ).lower()

            if not self._license_allowed(
                license_text
            ):
                continue

            source_url = str(
                info.get(
                    "descriptionurl",
                    "",
                )
                or info.get(
                    "url",
                    "",
                )
            ).strip()

            if mime.startswith("video/"):
                # Video assets must download the actual video,
                # never the image thumbnail.
                media_url = str(
                    info.get(
                        "url",
                        "",
                    )
                ).strip()
            else:
                # Images use a smaller Wikimedia thumbnail
                # when available to reduce bandwidth/rate limits.
                media_url = str(
                    info.get(
                        "thumburl",
                        "",
                    )
                    or info.get(
                        "url",
                        "",
                    )
                ).strip()

            if not media_url:
                continue

            title = str(
                page.get(
                    "title",
                    "media",
                )
            )

            relevance = self._relevance_score(
                query=query,
                title=title,
                rank=rank,
            )

            if relevance < 65.0:
                continue

            suffix = self._suffix_from_url(
                media_url,
                mime,
            )

            filename = (
                f"{uuid4().hex[:12]}"
                f"{suffix}"
            )

            destination = (
                output_dir / filename
            )

            try:
                self._download(
                    media_url,
                    destination,
                )

            except urllib.error.HTTPError as exc:

                if exc.code == 429:
                    # One throttled asset must not abort the
                    # entire production cycle. Continue searching
                    # for another explicitly licensed candidate.
                    continue

                raise

            except Exception:
                # Media-provider failure is isolated to this
                # candidate. Other search results may still work.
                continue

            creator = self._clean_html(
                self._meta(
                    metadata,
                    "Artist",
                )
            )

            license_url = self._meta(
                metadata,
                "LicenseUrl",
            )

            attribution_required = not (
                "public domain"
                in license_text
                or "cc0"
                in license_text
            )

            asset_type = (
                "video"
                if mime.startswith("video/")
                else "image"
            )

            assets.append(
                MediaAsset(
                    asset_id=uuid4().hex,
                    asset_type=asset_type,
                    file_path=str(
                        destination
                    ),
                    source_url=source_url,
                    source_name=(
                        "Wikimedia Commons"
                    ),
                    creator=creator or None,
                    license_name=(
                        license_name
                        or usage_terms
                        or None
                    ),
                    license_url=(
                        license_url or None
                    ),
                    attribution_required=(
                        attribution_required
                    ),
                    commercial_use_allowed=True,
                    relevance_score=relevance,
                    content_id=content_id,
                )
            )

        return assets

    def _api(
        self,
        params: dict[str, str],
    ) -> dict:

        url = (
            self.API_URL
            + "?"
            + urllib.parse.urlencode(
                params
            )
        )

        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": self.USER_AGENT,
            },
        )

        with urllib.request.urlopen(
            request,
            timeout=30,
        ) as response:

            return json.loads(
                response.read().decode(
                    "utf-8"
                )
            )

    def _download(
        self,
        url: str,
        destination: Path,
    ) -> None:

        if destination.exists():
            return

        attempts = 3

        for attempt in range(
            1,
            attempts + 1,
        ):

            request = urllib.request.Request(
                url,
                headers={
                    "User-Agent": self.USER_AGENT,
                },
            )

            try:

                with urllib.request.urlopen(
                    request,
                    timeout=60,
                ) as response:

                    destination.write_bytes(
                        response.read()
                    )

                # Small courtesy delay between successful
                # Wikimedia media requests.
                time.sleep(1.25)

                return

            except urllib.error.HTTPError as exc:

                if (
                    exc.code == 429
                    and attempt < attempts
                ):

                    retry_after = (
                        exc.headers.get(
                            "Retry-After"
                        )
                        if exc.headers
                        else None
                    )

                    try:
                        delay = float(
                            retry_after
                        )
                    except (
                        TypeError,
                        ValueError,
                    ):
                        delay = min(
                            3.0 * attempt,
                            10.0,
                        )

                    time.sleep(
                        max(delay, 2.0)
                    )

                    continue

                raise

        raise RuntimeError(
            "Wikimedia media download failed "
            "after retry attempts."
        )
    def _license_allowed(
        self,
        text: str,
    ) -> bool:

        return any(
            marker in text
            for marker in self.ALLOWED_LICENSE_MARKERS
        )

    @staticmethod
    def _meta(
        metadata: dict,
        key: str,
    ) -> str:

        value = metadata.get(
            key,
            {},
        )

        if isinstance(value, dict):
            return str(
                value.get(
                    "value",
                    "",
                )
            ).strip()

        return ""

    @staticmethod
    def _clean_html(
        value: str,
    ) -> str:

        value = re.sub(
            r"<[^>]+>",
            " ",
            value,
        )

        value = html.unescape(
            value
        )

        return " ".join(
            value.split()
        )

    @staticmethod
    def _safe_name(
        value: str,
    ) -> str:

        cleaned = "".join(
            c if (
                c.isalnum()
                or c in "-_"
            )
            else "_"
            for c in value
        )

        return cleaned[:80] or "unknown"

    @staticmethod
    def _suffix_from_url(
        url: str,
        mime: str,
    ) -> str:

        suffix = Path(
            urllib.parse.urlparse(
                url
            ).path
        ).suffix.lower()

        if suffix:
            return suffix

        mapping = {
            "image/jpeg": ".jpg",
            "image/png": ".png",
            "image/webp": ".webp",
            "video/webm": ".webm",
            "video/mp4": ".mp4",
            "video/ogg": ".ogv",
        }

        return mapping.get(
            mime,
            ".bin",
        )

    @staticmethod
    def _relevance_score(
        *,
        query: str,
        title: str,
        rank: int,
    ) -> float:

        stopwords = {
            "the",
            "a",
            "an",
            "and",
            "or",
            "of",
            "to",
            "in",
            "on",
            "for",
            "how",
            "why",
            "what",
            "is",
            "are",
        }

        query_words = {
            word
            for word in re.findall(
                r"[a-z0-9]+",
                query.lower(),
            )
            if (
                len(word) >= 3
                and word not in stopwords
            )
        }

        title_words = set(
            re.findall(
                r"[a-z0-9]+",
                title.lower(),
            )
        )

        overlap = len(
            query_words & title_words
        )

        if not query_words:
            semantic = 0.0
        else:
            semantic = (
                overlap
                / len(query_words)
            )

        rank_bonus = max(
            0.0,
            18.0 - (rank - 1) * 1.5,
        )

        return min(
            100.0,
            60.0
            + semantic * 30.0
            + rank_bonus,
        )








