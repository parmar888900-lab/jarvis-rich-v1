"""NASA Images video provider for Jarvis Rich V1."""

from __future__ import annotations

import hashlib
import json
import urllib.parse
import urllib.request
from pathlib import Path

from backend.services.video.media_asset import MediaAsset


class NasaVideoProvider:
    """
    Search NASA Images for topic-specific video material.

    NASA Images provides searchable media metadata through its
    official API. This provider uses video results only.
    """

    SOURCE_NAME = "NASA Images"

    SEARCH_URL = (
        "https://images-api.nasa.gov/search"
    )

    ASSET_URL = (
        "https://images-api.nasa.gov/asset/{nasa_id}"
    )

    MAX_DOWNLOAD_BYTES = (
        500 * 1024 * 1024
    )

    VIDEO_EXTENSIONS = {
        ".mp4",
        ".m4v",
        ".mov",
        ".webm",
    }

    def __init__(
        self,
        *,
        download_root: str = (
            "generated/media/nasa"
        ),
    ) -> None:

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

        results = self._search(
            clean_query
        )

        output: list[
            MediaAsset
        ] = []

        for item in results:

            if len(output) >= limit:
                break

            data_rows = item.get(
                "data",
                [],
            )

            if not data_rows:
                continue

            metadata = data_rows[0]

            nasa_id = str(
                metadata.get(
                    "nasa_id",
                    "",
                )
            ).strip()

            if not nasa_id:
                continue

            asset_url = self._best_video_url(
                nasa_id
            )

            if not asset_url:
                continue

            local_path = self._download(
                url=asset_url,
                content_id=content_id,
                nasa_id=nasa_id,
            )

            if local_path is None:
                continue

            title = str(
                metadata.get(
                    "title",
                    nasa_id,
                )
            )

            asset_id = (
                "nasa-"
                + hashlib.sha1(
                    (
                        nasa_id
                        + "|"
                        + asset_url
                    ).encode(
                        "utf-8"
                    )
                ).hexdigest()[:14]
            )

            output.append(
                MediaAsset(
                    asset_id=asset_id,
                    asset_type="video",
                    file_path=str(
                        local_path
                    ),
                    source_url=asset_url,
                    source_name=(
                        self.SOURCE_NAME
                    ),
                    creator=str(
                        metadata.get(
                            "center",
                            "NASA",
                        )
                        or "NASA"
                    ),
                    license_name=(
                        "NASA Media"
                    ),
                    license_url=(
                        "https://www.nasa.gov/nasa-brand-center/images-and-media/"
                    ),
                    attribution_required=False,
                    commercial_use_allowed=True,
                    relevance_score=80.0,
                    content_id=content_id,
                )
            )

        return output

    def _search(
        self,
        query: str,
    ) -> list[dict]:

        params = urllib.parse.urlencode(
            {
                "q": query,
                "media_type": "video",
                "page_size": 25,
            }
        )

        url = (
            self.SEARCH_URL
            + "?"
            + params
        )

        try:

            with urllib.request.urlopen(
                url,
                timeout=30,
            ) as response:

                data = json.loads(
                    response.read().decode(
                        "utf-8",
                        errors="replace",
                    )
                )

        except Exception:
            return []

        return (
            data.get(
                "collection",
                {},
            ).get(
                "items",
                [],
            )
            or []
        )

    def _best_video_url(
        self,
        nasa_id: str,
    ) -> str | None:

        url = (
            self.ASSET_URL.format(
                nasa_id=(
                    urllib.parse.quote(
                        nasa_id,
                        safe="",
                    )
                )
            )
        )

        try:

            with urllib.request.urlopen(
                url,
                timeout=30,
            ) as response:

                data = json.loads(
                    response.read().decode(
                        "utf-8",
                        errors="replace",
                    )
                )

        except Exception:
            return None

        items = (
            data.get(
                "collection",
                {},
            ).get(
                "items",
                [],
            )
            or []
        )

        candidates = []

        for item in items:

            href = str(
                item.get(
                    "href",
                    "",
                )
            ).strip()

            if not href:
                continue

            parsed = urllib.parse.urlparse(
                href
            )

            suffix = Path(
                parsed.path
            ).suffix.lower()

            if (
                suffix
                not in self.VIDEO_EXTENSIONS
            ):
                continue

            lower = href.lower()

            score = 0

            if suffix == ".mp4":
                score += 30

            if "orig" in lower:
                score += 10

            if "large" in lower:
                score += 8

            if "medium" in lower:
                score += 5

            candidates.append(
                (
                    score,
                    href,
                )
            )

        if not candidates:
            return None

        candidates.sort(
            reverse=True,
            key=lambda row: row[0],
        )

        return candidates[0][1]

    def _download(
        self,
        *,
        url: str,
        content_id: str,
        nasa_id: str,
    ) -> Path | None:

        parsed = urllib.parse.urlparse(
            url
        )

        suffix = (
            Path(
                parsed.path
            ).suffix.lower()
            or ".mp4"
        )

        digest = hashlib.sha1(
            url.encode(
                "utf-8"
            )
        ).hexdigest()[:16]

        safe_id = "".join(
            character
            if character.isalnum()
            else "_"
            for character in nasa_id
        )[:40]

        output = (
            self.download_root
            / (
                f"{content_id}_"
                f"{safe_id}_"
                f"{digest}"
                f"{suffix}"
            )
        )

        if (
            output.exists()
            and output.stat().st_size > 0
        ):
            return output

        temp = output.with_suffix(
            output.suffix + ".part"
        )

        try:

            request = urllib.request.Request(
                url,
                headers={
                    "User-Agent": (
                        "JarvisRichV1/1.0"
                    ),
                },
            )

            with urllib.request.urlopen(
                request,
                timeout=90,
            ) as response:

                with temp.open(
                    "wb"
                ) as handle:

                    total = 0

                    while True:

                        chunk = response.read(
                            1024 * 1024
                        )

                        if not chunk:
                            break

                        total += len(
                            chunk
                        )

                        if (
                            total
                            > self.MAX_DOWNLOAD_BYTES
                        ):
                            raise RuntimeError(
                                "NASA video exceeds "
                                "download limit."
                            )

                        handle.write(
                            chunk
                        )

            temp.replace(
                output
            )

        except Exception:

            try:
                temp.unlink(
                    missing_ok=True
                )
            except OSError:
                pass

            return None

        return output
