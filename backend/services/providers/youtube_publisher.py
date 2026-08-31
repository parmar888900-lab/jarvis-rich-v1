"""Authenticated YouTube video publishing provider."""

from __future__ import annotations

import asyncio
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

from backend.services.orchestration.uncertain_side_effect import (
    UncertainSideEffectError,
)


YOUTUBE_SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]


class YoutubePublisherError(RuntimeError):
    """Base publishing-provider error."""


class YoutubeAuthorizationRequired(
    YoutubePublisherError
):
    """Raised when no usable OAuth authorization exists."""


class YoutubeUploadUncertainError(
    UncertainSideEffectError
):
    """Raised when YouTube may have accepted an upload."""


def build_youtube_operation_tag(
    idempotency_key: str,
) -> str:
    """Build a deterministic provider-visible marker."""

    clean_key = idempotency_key.strip()

    if not clean_key:
        raise ValueError(
            "idempotency_key cannot be empty."
        )

    digest = hashlib.sha256(
        clean_key.encode("utf-8")
    ).hexdigest()

    return (
        "jarvis-op-"
        f"{digest[:32]}"
    )


@dataclass(frozen=True)
class YoutubePublisherConfig:
    """Filesystem configuration for YouTube OAuth."""

    client_secret_path: Path = Path(
        "secrets/youtube_client_secret.json"
    )

    token_path: Path = Path(
        "secrets/youtube_token.json"
    )


class YoutubePublisher:
    """Upload videos to an authorized YouTube channel."""

    def __init__(
        self,
        config: YoutubePublisherConfig | None = None,
    ) -> None:
        self.config = (
            config
            if config is not None
            else YoutubePublisherConfig()
        )

    def _save_credentials(
        self,
        credentials: Credentials,
    ) -> None:
        self.config.token_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.config.token_path.write_text(
            credentials.to_json(),
            encoding="utf-8",
        )

    def _load_credentials(
        self,
    ) -> Credentials:
        token_path = self.config.token_path

        if not token_path.exists():
            raise YoutubeAuthorizationRequired(
                "YouTube OAuth authorization is required. "
                "Run the explicit authorization flow first."
            )

        credentials = Credentials.from_authorized_user_file(
            str(token_path),
            scopes=YOUTUBE_SCOPES,
        )

        if (
            credentials.expired
            and credentials.refresh_token
        ):
            credentials.refresh(
                Request()
            )

            self._save_credentials(
                credentials
            )

        if not credentials.valid:
            raise YoutubeAuthorizationRequired(
                "Stored YouTube authorization is invalid "
                "or cannot be refreshed."
            )

        return credentials

    def authorize_interactively(
        self,
    ) -> dict:
        """Perform the one-time browser OAuth authorization."""

        client_secret_path = (
            self.config.client_secret_path
        )

        if not client_secret_path.exists():
            raise YoutubeAuthorizationRequired(
                "OAuth client file is missing: "
                f"{client_secret_path}"
            )

        flow = InstalledAppFlow.from_client_secrets_file(
            str(client_secret_path),
            scopes=YOUTUBE_SCOPES,
        )

        credentials = flow.run_local_server(
            host="127.0.0.1",
            port=0,
            open_browser=True,
            authorization_prompt_message=(
                "Opening Google authorization..."
            ),
            success_message=(
                "Jarvis YouTube authorization completed. "
                "You may close this browser tab."
            ),
        )

        self._save_credentials(
            credentials
        )

        return {
            "status": "authorized",
            "token_path": str(
                self.config.token_path
            ),
        }

    def get_authorized_channel(
        self,
    ) -> dict:
        """Return the channel authorized by the stored OAuth token."""

        client = self._build_client()

        response = (
            client.channels()
            .list(
                part="id,snippet",
                mine=True,
            )
            .execute()
        )

        items = response.get(
            "items",
            [],
        )

        if not items:
            raise YoutubePublisherError(
                "No YouTube channel is associated "
                "with the authorized account."
            )

        channel = items[0]

        snippet = channel.get(
            "snippet",
            {},
        )

        channel_id = str(
            channel.get(
                "id",
                "",
            )
        ).strip()

        title = str(
            snippet.get(
                "title",
                "",
            )
        ).strip()

        if not channel_id:
            raise YoutubePublisherError(
                "Authorized YouTube channel did "
                "not return a channel ID."
            )

        return {
            "status": "authorized",
            "channel_id": channel_id,
            "channel_title": title,
        }

    def _build_client(
        self,
    ) -> Any:
        credentials = self._load_credentials()

        return build(
            "youtube",
            "v3",
            credentials=credentials,
            cache_discovery=False,
        )

    def get_video_statistics(
        self,
        video_ids: list[str],
    ) -> list[dict]:
        """Return normalized statistics for YouTube videos."""

        cleaned_ids: list[str] = []

        for video_id in video_ids:
            clean_id = str(
                video_id
            ).strip()

            if (
                clean_id
                and clean_id not in cleaned_ids
            ):
                cleaned_ids.append(
                    clean_id
                )

        if not cleaned_ids:
            return []

        client = self._build_client()

        results: list[dict] = []

        for offset in range(
            0,
            len(cleaned_ids),
            50,
        ):
            batch = cleaned_ids[
                offset:offset + 50
            ]

            response = (
                client.videos()
                .list(
                    part=(
                        "id,snippet,statistics,"
                        "status"
                    ),
                    id=",".join(batch),
                    maxResults=len(batch),
                )
                .execute()
            )

            for item in response.get(
                "items",
                [],
            ):
                video_id = str(
                    item.get(
                        "id",
                        "",
                    )
                ).strip()

                if not video_id:
                    continue

                snippet = item.get(
                    "snippet",
                    {},
                )

                statistics = item.get(
                    "statistics",
                    {},
                )

                status = item.get(
                    "status",
                    {},
                )

                def parse_count(
                    key: str,
                ) -> int:
                    try:
                        return max(
                            int(
                                statistics.get(
                                    key,
                                    0,
                                )
                                or 0
                            ),
                            0,
                        )
                    except (
                        TypeError,
                        ValueError,
                    ):
                        return 0

                results.append(
                    {
                        "video_id": video_id,
                        "channel_id": str(
                            snippet.get(
                                "channelId",
                                "",
                            )
                        ).strip(),
                        "title": str(
                            snippet.get(
                                "title",
                                "",
                            )
                        ).strip(),
                        "published_at": str(
                            snippet.get(
                                "publishedAt",
                                "",
                            )
                        ).strip(),
                        "privacy_status": str(
                            status.get(
                                "privacyStatus",
                                "",
                            )
                        ).strip(),
                        "views": parse_count(
                            "viewCount"
                        ),
                        "likes": parse_count(
                            "likeCount"
                        ),
                        "comments": parse_count(
                            "commentCount"
                        ),
                    }
                )

        result_by_id = {
            item["video_id"]: item
            for item in results
        }

        return [
            result_by_id[video_id]
            for video_id in cleaned_ids
            if video_id in result_by_id
        ]

    @staticmethod
    def _validate_video_path(
        video_path: Path,
    ) -> Path:
        path = video_path.expanduser().resolve()

        if not path.exists():
            raise FileNotFoundError(
                f"Video does not exist: {path}"
            )

        if not path.is_file():
            raise ValueError(
                f"Video path is not a file: {path}"
            )

        return path

    def _upload_sync(
        self,
        *,
        video_path: Path,
        title: str,
        description: str,
        tags: list[str] | None,
        privacy_status: str,
        category_id: str,
        operation_tag: str | None = None,
    ) -> dict:
        path = self._validate_video_path(
            video_path
        )

        cleaned_title = title.strip()

        if not cleaned_title:
            raise ValueError(
                "YouTube title cannot be empty."
            )

        allowed_privacy = {
            "private",
            "unlisted",
            "public",
        }

        if privacy_status not in allowed_privacy:
            raise ValueError(
                "privacy_status must be private, "
                "unlisted, or public."
            )

        client = self._build_client()

        snippet: dict[str, Any] = {
            "title": cleaned_title,
            "description": description.strip(),
            "categoryId": str(category_id),
        }

        cleaned_tags = [
            tag.strip()
            for tag in (tags or [])
            if tag.strip()
        ]

        clean_operation_tag = (
            operation_tag.strip()
            if operation_tag is not None
            else ""
        )

        if (
            clean_operation_tag
            and clean_operation_tag not in cleaned_tags
        ):
            cleaned_tags.append(
                clean_operation_tag
            )

        if cleaned_tags:
            snippet["tags"] = cleaned_tags

        body = {
            "snippet": snippet,
            "status": {
                "privacyStatus": privacy_status,
                "selfDeclaredMadeForKids": False,
            },
        }

        with path.open("rb") as video_stream:
            media = MediaIoBaseUpload(
                video_stream,
                mimetype="video/mp4",
                chunksize=8 * 1024 * 1024,
                resumable=True,
            )

            request = client.videos().insert(
                part="snippet,status",
                body=body,
                media_body=media,
            )

            response = None

            while response is None:
                try:
                    _, response = request.next_chunk()

                except Exception as exc:
                    # Once transfer execution has begun,
                    # a client-side failure does not prove
                    # whether YouTube accepted the upload.
                    raise YoutubeUploadUncertainError(
                        "YouTube upload outcome is uncertain: "
                        f"{exc}"
                    ) from exc

        video_id = str(
            response.get("id", "")
        ).strip()

        if not video_id:
            # The provider returned from the resumable
            # upload flow, so the external video may
            # already exist even though its ID was not
            # returned to Jarvis. Never classify this as
            # a definitely failed upload.
            raise YoutubeUploadUncertainError(
                "YouTube upload returned without "
                "a video ID; provider state is uncertain."
            )

        return {
            "status": "uploaded",
            "video_id": video_id,
            "privacy_status": privacy_status,
            "title": cleaned_title,
        }

    def get_recent_upload_video_ids(
        self,
        *,
        max_items: int = 50,
    ) -> dict:
        """Return recent uploads for the authorized channel."""

        if max_items <= 0:
            raise ValueError(
                "max_items must be positive."
            )

        client = self._build_client()

        channel_response = (
            client.channels()
            .list(
                part="id,contentDetails",
                mine=True,
            )
            .execute()
        )

        channel_items = channel_response.get(
            "items",
            [],
        )

        if not channel_items:
            raise YoutubePublisherError(
                "Authorized channel was not returned."
            )

        channel = channel_items[0]

        channel_id = str(
            channel.get(
                "id",
                "",
            )
        ).strip()

        uploads_playlist_id = str(
            channel.get(
                "contentDetails",
                {},
            )
            .get(
                "relatedPlaylists",
                {},
            )
            .get(
                "uploads",
                "",
            )
        ).strip()

        if not channel_id:
            raise YoutubePublisherError(
                "Authorized channel ID is missing."
            )

        if not uploads_playlist_id:
            raise YoutubePublisherError(
                "Authorized channel uploads playlist "
                "is missing."
            )

        video_ids: list[str] = []
        seen: set[str] = set()
        page_token = None

        while len(video_ids) < max_items:

            request_kwargs = {
                "part": "contentDetails",
                "playlistId": uploads_playlist_id,
                "maxResults": min(
                    50,
                    max_items - len(video_ids),
                ),
            }

            if page_token:
                request_kwargs[
                    "pageToken"
                ] = page_token

            response = (
                client.playlistItems()
                .list(
                    **request_kwargs
                )
                .execute()
            )

            for item in response.get(
                "items",
                [],
            ):
                video_id = str(
                    item.get(
                        "contentDetails",
                        {},
                    ).get(
                        "videoId",
                        "",
                    )
                ).strip()

                if (
                    video_id
                    and video_id not in seen
                ):
                    seen.add(video_id)
                    video_ids.append(
                        video_id
                    )

                if len(video_ids) >= max_items:
                    break

            page_token = response.get(
                "nextPageToken"
            )

            if not page_token:
                break

        return {
            "channel_id": channel_id,
            "uploads_playlist_id": (
                uploads_playlist_id
            ),
            "video_ids": video_ids,
        }


    def find_uploaded_video_by_operation_tag(
        self,
        operation_tag: str,
        *,
        max_items: int = 200,
    ) -> dict | None:
        """Find a recent authorized-channel upload by marker.

        Absence from this bounded scan is not proof
        that the upload never occurred.
        """

        tag = operation_tag.strip()

        if not tag:
            raise ValueError(
                "operation_tag cannot be empty."
            )

        if max_items <= 0:
            raise ValueError(
                "max_items must be positive."
            )

        client = self._build_client()

        channel_response = (
            client.channels()
            .list(
                part="id,contentDetails",
                mine=True,
            )
            .execute()
        )

        channel_items = channel_response.get(
            "items",
            [],
        )

        if not channel_items:
            raise YoutubePublisherError(
                "Authorized channel was not returned "
                "during reconciliation."
            )

        channel = channel_items[0]

        channel_id = str(
            channel.get(
                "id",
                "",
            )
        ).strip()

        uploads_playlist_id = str(
            channel.get(
                "contentDetails",
                {},
            )
            .get(
                "relatedPlaylists",
                {},
            )
            .get(
                "uploads",
                "",
            )
        ).strip()

        if not channel_id:
            raise YoutubePublisherError(
                "Authorized channel ID is missing "
                "during reconciliation."
            )

        if not uploads_playlist_id:
            raise YoutubePublisherError(
                "Authorized channel uploads playlist "
                "is missing."
            )

        video_ids: list[str] = []

        page_token = None

        while len(video_ids) < max_items:

            request_kwargs = {
                "part": "contentDetails",
                "playlistId": uploads_playlist_id,
                "maxResults": min(
                    50,
                    max_items - len(video_ids),
                ),
            }

            if page_token:
                request_kwargs[
                    "pageToken"
                ] = page_token

            response = (
                client.playlistItems()
                .list(
                    **request_kwargs
                )
                .execute()
            )

            for item in response.get(
                "items",
                [],
            ):
                video_id = str(
                    item.get(
                        "contentDetails",
                        {},
                    ).get(
                        "videoId",
                        "",
                    )
                ).strip()

                if video_id:
                    video_ids.append(
                        video_id
                    )

                if len(video_ids) >= max_items:
                    break

            page_token = response.get(
                "nextPageToken"
            )

            if not page_token:
                break

        for offset in range(
            0,
            len(video_ids),
            50,
        ):

            batch = video_ids[
                offset:offset + 50
            ]

            if not batch:
                continue

            response = (
                client.videos()
                .list(
                    part="snippet",
                    id=",".join(batch),
                    maxResults=len(batch),
                )
                .execute()
            )

            for item in response.get(
                "items",
                [],
            ):

                snippet = item.get(
                    "snippet",
                    {},
                )

                tags = [
                    str(value).strip()
                    for value in (
                        snippet.get(
                            "tags",
                            [],
                        )
                        or []
                    )
                ]

                if tag not in tags:
                    continue

                video_id = str(
                    item.get(
                        "id",
                        "",
                    )
                ).strip()

                if not video_id:
                    continue

                return {
                    "channel_id": channel_id,
                    "video_id": video_id,
                    "title": str(
                        snippet.get(
                            "title",
                            "",
                        )
                    ).strip(),
                    "operation_tag": tag,
                }

        return None

    async def upload_video(
        self,
        *,
        video_path: str | Path,
        title: str,
        description: str = "",
        tags: list[str] | None = None,
        privacy_status: str = "private",
        category_id: str = "22",
        operation_tag: str | None = None,
    ) -> dict:
        """Upload without blocking the async event loop."""

        return await asyncio.to_thread(
            self._upload_sync,
            video_path=Path(video_path),
            title=title,
            description=description,
            tags=tags,
            privacy_status=privacy_status,
            category_id=category_id,
            operation_tag=operation_tag,
        )
