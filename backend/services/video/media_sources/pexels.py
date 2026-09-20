"""Pexels licensed-media provider for Jarvis Rich V1."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import urllib.parse
import urllib.request
from pathlib import Path

from backend.services.video.media_asset import MediaAsset


class PexelsProvider:
    """
    Search and download Pexels photos/videos for contextual B-roll.

    Pexels assets are treated as contextual licensed media, not as
    authentic footage from the movie being discussed.
    """

    API_BASE = "https://api.pexels.com"
    SOURCE_NAME = "Pexels"
    LICENSE_NAME = "Pexels License"
    LICENSE_URL = "https://www.pexels.com/license/"

    DEFAULT_TIMEOUT = 25

    def __init__(
        self,
        *,
        api_key: str | None = None,
        download_root: str = "generated/media/pexels",
    ) -> None:

        self.api_key = (
            api_key
            or os.environ.get(
                "PEXELS_API_KEY",
                "",
            )
        ).strip()

        if not self.api_key:
            raise RuntimeError(
                "PEXELS_API_KEY is not configured."
            )

        self.download_root = Path(
            download_root
        )

        self.download_root.mkdir(
            parents=True,
            exist_ok=True,
        )

    async def search_and_download(
        self,
        *,
        query: str,
        content_id: str,
        limit: int = 2,
    ) -> list[MediaAsset]:

        clean_query = " ".join(
            str(query).split()
        ).strip()

        if not clean_query:
            return []

        clean_content_id = str(
            content_id
        ).strip()

        if not clean_content_id:
            raise RuntimeError(
                "Pexels search requires content_id."
            )

        safe_limit = max(
            1,
            min(
                int(limit),
                5,
            ),
        )

        ####################################################
        # Prefer video because movie commentary benefits
        # from motion. Fall back to photos.
        ####################################################

        video_results = await asyncio.to_thread(
            self._search_videos,
            clean_query,
            safe_limit,
        )

        assets = []

        for item in video_results:

            asset = await asyncio.to_thread(
                self._download_video,
                item,
                clean_query,
                clean_content_id,
            )

            if asset is not None:
                assets.append(asset)

            if len(assets) >= safe_limit:
                return assets

        remaining = (
            safe_limit - len(assets)
        )

        if remaining <= 0:
            return assets

        photo_results = await asyncio.to_thread(
            self._search_photos,
            clean_query,
            remaining,
        )

        for item in photo_results:

            asset = await asyncio.to_thread(
                self._download_photo,
                item,
                clean_query,
                clean_content_id,
            )

            if asset is not None:
                assets.append(asset)

            if len(assets) >= safe_limit:
                break

        return assets

    ########################################################
    # API
    ########################################################

    def _request_json(
        self,
        url: str,
    ) -> dict:

        request = urllib.request.Request(
            url,
            headers={
                "Authorization": self.api_key,
                "User-Agent": (
                    "Jarvis-Rich-V1/1.0"
                ),
            },
        )

        with urllib.request.urlopen(
            request,
            timeout=self.DEFAULT_TIMEOUT,
        ) as response:

            payload = response.read()

        data = json.loads(
            payload.decode("utf-8")
        )

        if not isinstance(data, dict):
            return {}

        return data

    def _search_videos(
        self,
        query: str,
        limit: int,
    ) -> list[dict]:

        params = urllib.parse.urlencode(
            {
                "query": query,
                "per_page": limit,
                "orientation": "portrait",
            }
        )

        data = self._request_json(
            f"{self.API_BASE}/videos/search?{params}"
        )

        videos = data.get(
            "videos",
            [],
        )

        if not isinstance(videos, list):
            return []

        return [
            item
            for item in videos
            if isinstance(item, dict)
        ]

    def _search_photos(
        self,
        query: str,
        limit: int,
    ) -> list[dict]:

        params = urllib.parse.urlencode(
            {
                "query": query,
                "per_page": limit,
                "orientation": "portrait",
            }
        )

        data = self._request_json(
            f"{self.API_BASE}/v1/search?{params}"
        )

        photos = data.get(
            "photos",
            [],
        )

        if not isinstance(photos, list):
            return []

        return [
            item
            for item in photos
            if isinstance(item, dict)
        ]

    ########################################################
    # VIDEO
    ########################################################

    def _download_video(
        self,
        item: dict,
        query: str,
        content_id: str,
    ) -> MediaAsset | None:

        video_id = str(
            item.get(
                "id",
                "",
            )
        ).strip()

        source_url = str(
            item.get(
                "url",
                "",
            )
        ).strip()

        creator = ""

        user = item.get(
            "user",
            {},
        )

        if isinstance(user, dict):
            creator = str(
                user.get(
                    "name",
                    "",
                )
            ).strip()

        files = item.get(
            "video_files",
            [],
        )

        if not isinstance(files, list):
            return None

        usable = []

        for file_info in files:

            if not isinstance(
                file_info,
                dict,
            ):
                continue

            link = str(
                file_info.get(
                    "link",
                    "",
                )
            ).strip()

            file_type = str(
                file_info.get(
                    "file_type",
                    "",
                )
            ).lower()

            width = self._int_or_none(
                file_info.get(
                    "width"
                )
            )

            height = self._int_or_none(
                file_info.get(
                    "height"
                )
            )

            if not link:
                continue

            if "mp4" not in file_type:
                continue

            usable.append(
                (
                    width or 0,
                    height or 0,
                    link,
                    width,
                    height,
                )
            )

        if not usable:
            return None

        ####################################################
        # Prefer useful resolution without blindly taking
        # the largest available file.
        ####################################################

        usable.sort(
            key=lambda item: (
                item[1] >= 1080,
                item[0] >= 720,
                item[0] * item[1],
            ),
            reverse=True,
        )

        (
            _,
            _,
            download_url,
            width,
            height,
        ) = usable[0]

        filename = self._filename(
            content_id=content_id,
            media_id=video_id,
            extension=".mp4",
        )

        destination = (
            self.download_root
            / filename
        )

        if not destination.exists():

            if not self._download(
                download_url,
                destination,
            ):
                return None

        relevance = self._relevance_score(
            query=query,
            item_text=" ".join(
                [
                    source_url,
                    creator,
                ]
            ),
        )

        return MediaAsset(
            asset_id=(
                f"pexels-video-{video_id}"
            ),
            asset_type="video",
            file_path=str(destination),
            source_url=source_url,
            source_name=self.SOURCE_NAME,
            creator=creator or None,
            license_name=self.LICENSE_NAME,
            license_url=self.LICENSE_URL,
            attribution_required=False,
            commercial_use_allowed=True,
            relevance_score=relevance,
            duration=self._float_or_none(
                item.get(
                    "duration"
                )
            ),
            width=width,
            height=height,
            content_id=content_id,
        )

    ########################################################
    # PHOTO
    ########################################################

    def _download_photo(
        self,
        item: dict,
        query: str,
        content_id: str,
    ) -> MediaAsset | None:

        photo_id = str(
            item.get(
                "id",
                "",
            )
        ).strip()

        source_url = str(
            item.get(
                "url",
                "",
            )
        ).strip()

        creator = str(
            item.get(
                "photographer",
                "",
            )
        ).strip()

        src = item.get(
            "src",
            {},
        )

        if not isinstance(src, dict):
            return None

        download_url = str(
            src.get(
                "large2x"
            )
            or src.get(
                "large"
            )
            or src.get(
                "original"
            )
            or ""
        ).strip()

        if not download_url:
            return None

        filename = self._filename(
            content_id=content_id,
            media_id=photo_id,
            extension=".jpg",
        )

        destination = (
            self.download_root
            / filename
        )

        if not destination.exists():

            if not self._download(
                download_url,
                destination,
            ):
                return None

        width = self._int_or_none(
            item.get(
                "width"
            )
        )

        height = self._int_or_none(
            item.get(
                "height"
            )
        )

        alt = str(
            item.get(
                "alt",
                "",
            )
        ).strip()

        relevance = self._relevance_score(
            query=query,
            item_text=" ".join(
                [
                    alt,
                    source_url,
                    creator,
                ]
            ),
        )

        return MediaAsset(
            asset_id=(
                f"pexels-photo-{photo_id}"
            ),
            asset_type="image",
            file_path=str(destination),
            source_url=source_url,
            source_name=self.SOURCE_NAME,
            creator=creator or None,
            license_name=self.LICENSE_NAME,
            license_url=self.LICENSE_URL,
            attribution_required=False,
            commercial_use_allowed=True,
            relevance_score=relevance,
            width=width,
            height=height,
            content_id=content_id,
        )

    ########################################################
    # Helpers
    ########################################################

    @staticmethod
    def _download(
        url: str,
        destination: Path,
    ) -> bool:

        try:

            request = urllib.request.Request(
                url,
                headers={
                    "User-Agent": (
                        "Jarvis-Rich-V1/1.0"
                    ),
                },
            )

            with urllib.request.urlopen(
                request,
                timeout=30,
            ) as response:

                data = response.read()

            if not data:
                return False

            destination.write_bytes(
                data
            )

            return True

        except Exception:
            return False

    @staticmethod
    def _filename(
        *,
        content_id: str,
        media_id: str,
        extension: str,
    ) -> str:

        safe_content = re.sub(
            r"[^A-Za-z0-9_-]+",
            "_",
            content_id,
        )[:60]

        digest = hashlib.sha1(
            str(media_id).encode(
                "utf-8"
            )
        ).hexdigest()[:12]

        return (
            f"{safe_content}_"
            f"{digest}"
            f"{extension}"
        )

    @staticmethod
    def _relevance_score(
        *,
        query: str,
        item_text: str,
    ) -> float:
        """
        Conservative lexical relevance estimate.

        This deliberately does not award high relevance merely
        because Pexels returned an item.
        """

        query_terms = {
            word
            for word in re.findall(
                r"[a-z0-9]+",
                query.lower(),
            )
            if len(word) >= 4
        }

        item_terms = {
            word
            for word in re.findall(
                r"[a-z0-9]+",
                item_text.lower(),
            )
            if len(word) >= 4
        }

        if not query_terms:
            return 0.0

        shared = (
            query_terms
            .intersection(
                item_terms
            )
        )

        ratio = (
            len(shared)
            / len(query_terms)
        )

        return round(
            min(
                95.0,
                60.0
                + ratio * 35.0,
            ),
            1,
        )

    @staticmethod
    def _int_or_none(
        value,
    ) -> int | None:

        try:
            return int(value)
        except (
            TypeError,
            ValueError,
        ):
            return None

    @staticmethod
    def _float_or_none(
        value,
    ) -> float | None:

        try:
            return float(value)
        except (
            TypeError,
            ValueError,
        ):
            return None
