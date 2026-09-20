"""Internet Archive reusable-video provider for Jarvis Rich V1."""

from __future__ import annotations

import hashlib
import json
import urllib.parse
import urllib.request
from pathlib import Path

from backend.services.video.media_asset import MediaAsset


class InternetArchiveProvider:
    """
    Find downloadable video on Internet Archive.

    Fail-closed:
    only items with explicit Creative Commons or public-domain
    license metadata are eligible.
    """

    SOURCE_NAME = "Internet Archive"

    SEARCH_URL = (
        "https://archive.org/advancedsearch.php"
    )

    METADATA_URL = (
        "https://archive.org/metadata/{identifier}"
    )

    DOWNLOAD_URL = (
        "https://archive.org/download/"
        "{identifier}/{filename}"
    )

    VIDEO_EXTENSIONS = {
        ".mp4",
        ".m4v",
        ".webm",
        ".mov",
    }

    MAX_DOWNLOAD_BYTES = (
        500 * 1024 * 1024
    )

    def __init__(
        self,
        *,
        download_root: str = (
            "generated/media/internet_archive"
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

        clean_content_id = " ".join(
            str(content_id).split()
        ).strip()

        if not clean_query:
            return []

        if not clean_content_id:
            raise RuntimeError(
                "Internet Archive search requires content_id."
            )

        docs = self._search(
            clean_query,
            max(
                5,
                limit * 5,
            ),
        )

        output: list[MediaAsset] = []

        for doc in docs:

            if len(output) >= limit:
                break

            identifier = str(
                doc.get(
                    "identifier",
                    "",
                )
            ).strip()

            if not identifier:
                continue

            metadata = self._metadata(
                identifier
            )

            license_info = (
                self._license_info(
                    metadata
                )
            )

            if license_info is None:
                continue

            selected = self._best_video_file(
                metadata
            )

            if selected is None:
                continue

            filename = selected["name"]

            download_url = (
                self.DOWNLOAD_URL.format(
                    identifier=(
                        urllib.parse.quote(
                            identifier,
                            safe="",
                        )
                    ),
                    filename=(
                        urllib.parse.quote(
                            filename
                        )
                    ),
                )
            )

            local_path = (
                self._download(
                    url=download_url,
                    content_id=(
                        clean_content_id
                    ),
                    identifier=identifier,
                    filename=filename,
                )
            )

            if local_path is None:
                continue

            title = str(
                metadata.get(
                    "metadata",
                    {},
                ).get(
                    "title",
                    identifier,
                )
            )

            asset_id = (
                "archive-"
                + hashlib.sha1(
                    (
                        identifier
                        + "|"
                        + filename
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
                    source_url=download_url,
                    source_name=(
                        self.SOURCE_NAME
                    ),
                    creator=str(
                        metadata.get(
                            "metadata",
                            {},
                        ).get(
                            "creator",
                            "",
                        )
                        or ""
                    ),
                    license_name=(
                        license_info[
                            "license_name"
                        ]
                    ),
                    license_url=(
                        license_info[
                            "license_url"
                        ]
                    ),
                    attribution_required=(
                        license_info[
                            "attribution_required"
                        ]
                    ),
                    commercial_use_allowed=True,
                    relevance_score=72.0,
                    content_id=(
                        clean_content_id
                    ),
                )
            )

        return output

    def _search(
        self,
        query: str,
        rows: int,
    ) -> list[dict]:

        search_query = (
            f'({query}) AND mediatype:movies'
        )

        params = urllib.parse.urlencode(
            {
                "q": search_query,
                "fl[]": [
                    "identifier",
                    "title",
                ],
                "rows": rows,
                "page": 1,
                "output": "json",
            },
            doseq=True,
        )

        url = (
            self.SEARCH_URL
            + "?"
            + params
        )

        try:

            with urllib.request.urlopen(
                url,
                timeout=25,
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
                "response",
                {},
            ).get(
                "docs",
                [],
            )
            or []
        )

    def _metadata(
        self,
        identifier: str,
    ) -> dict:

        url = (
            self.METADATA_URL.format(
                identifier=(
                    urllib.parse.quote(
                        identifier,
                        safe="",
                    )
                )
            )
        )

        try:

            with urllib.request.urlopen(
                url,
                timeout=25,
            ) as response:

                return json.loads(
                    response.read().decode(
                        "utf-8",
                        errors="replace",
                    )
                )

        except Exception:
            return {}

    @staticmethod
    def _license_info(
        metadata: dict,
    ) -> dict | None:

        meta = metadata.get(
            "metadata",
            {},
        )

        raw = " ".join(
            str(
                meta.get(
                    key,
                    "",
                )
                or ""
            )
            for key in (
                "licenseurl",
                "rights",
                "license",
                "usage",
            )
        ).lower()

        license_url = str(
            meta.get(
                "licenseurl",
                "",
            )
            or ""
        )

        ####################################################
        # Fail closed on unclear rights.
        ####################################################

        if (
            "public domain" in raw
            or "creativecommons.org/publicdomain"
            in raw
            or "cc0" in raw
        ):

            return {
                "license_name": (
                    "Public domain / CC0"
                ),
                "license_url": (
                    license_url
                ),
                "attribution_required": False,
            }

        commercial_cc = (
            "creativecommons.org/licenses/by/"
            in raw
            or "creativecommons.org/licenses/by-sa/"
            in raw
            or "cc by " in raw
            or "cc-by " in raw
            or "cc by-sa" in raw
            or "cc-by-sa" in raw
        )

        if commercial_cc:

            return {
                "license_name": (
                    "Creative Commons"
                ),
                "license_url": (
                    license_url
                ),
                "attribution_required": True,
            }

        return None

    def _best_video_file(
        self,
        metadata: dict,
    ) -> dict | None:

        candidates = []

        for item in metadata.get(
            "files",
            [],
        ):

            name = str(
                item.get(
                    "name",
                    "",
                )
            )

            suffix = Path(
                name
            ).suffix.lower()

            if (
                suffix
                not in self.VIDEO_EXTENSIONS
            ):
                continue

            try:
                size = int(
                    item.get(
                        "size",
                        0,
                    )
                    or 0
                )
            except (
                TypeError,
                ValueError,
            ):
                size = 0

            if (
                size <= 0
                or size
                > self.MAX_DOWNLOAD_BYTES
            ):
                continue

            lower_name = name.lower()

            score = 0

            if suffix == ".mp4":
                score += 30

            if "512kb" in lower_name:
                score += 20

            if "h.264" in lower_name:
                score += 15

            if "derivative" in str(
                item.get(
                    "source",
                    "",
                )
            ).lower():
                score += 10

            candidates.append(
                (
                    score,
                    -size,
                    item,
                )
            )

        if not candidates:
            return None

        candidates.sort(
            reverse=True,
            key=lambda row: (
                row[0],
                row[1],
            ),
        )

        return candidates[0][2]

    def _download(
        self,
        *,
        url: str,
        content_id: str,
        identifier: str,
        filename: str,
    ) -> Path | None:

        digest = hashlib.sha1(
            (
                identifier
                + "|"
                + filename
            ).encode(
                "utf-8"
            )
        ).hexdigest()[:16]

        suffix = (
            Path(
                filename
            ).suffix.lower()
            or ".mp4"
        )

        output = (
            self.download_root
            / (
                f"{content_id}_"
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
                timeout=60,
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
                                "Archive video exceeds "
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
