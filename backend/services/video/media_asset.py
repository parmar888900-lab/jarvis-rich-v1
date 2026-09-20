"""Media asset model for Rich V1 licensed-media production."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class MediaAsset:
    """A production-approved visual asset."""

    asset_id: str
    asset_type: str
    file_path: str
    source_url: str
    source_name: str

    creator: str | None = None
    license_name: str | None = None
    license_url: str | None = None

    attribution_required: bool = False
    commercial_use_allowed: bool = False

    relevance_score: float = 0.0

    duration: float | None = None
    width: int | None = None
    height: int | None = None

    content_id: str | None = None

    @property
    def image_path(self) -> str:
        """Legacy renderer compatibility."""
        return self.file_path

    @property
    def provider(self) -> str:
        """Legacy production-package compatibility."""
        return self.source_name

    @property
    def prompt(self) -> str:
        """Legacy manifest compatibility."""
        return self.source_url

