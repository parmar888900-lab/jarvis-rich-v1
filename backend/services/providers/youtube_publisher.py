"""Authenticated YouTube video publishing provider."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload


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
                _, response = request.next_chunk()

        video_id = str(
            response.get("id", "")
        ).strip()

        if not video_id:
            raise YoutubePublisherError(
                "YouTube upload completed without "
                "returning a video ID."
            )

        return {
            "status": "uploaded",
            "video_id": video_id,
            "privacy_status": privacy_status,
            "title": cleaned_title,
        }

    async def upload_video(
        self,
        *,
        video_path: str | Path,
        title: str,
        description: str = "",
        tags: list[str] | None = None,
        privacy_status: str = "private",
        category_id: str = "22",
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
        )
