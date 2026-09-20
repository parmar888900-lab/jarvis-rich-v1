"""Licensed-media validation for Rich V1."""

from __future__ import annotations

from pathlib import Path

from backend.services.video.media_asset import MediaAsset


class AssetCollector:
    """
    Validate production media before it may enter the renderer.

    Search-engine availability is not permission to reuse an asset.
    Every asset must carry source, license, commercial-use, relevance,
    and production-cycle metadata.
    """

    MIN_RELEVANCE_SCORE = 65.0

    def validate_asset(
        self,
        asset: MediaAsset,
        *,
        content_id: str,
    ) -> tuple[bool, list[str]]:

        issues: list[str] = []

        path = Path(asset.file_path)

        if not path.exists():
            issues.append("asset_file_missing")

        if asset.asset_type not in {
            "video",
            "image",
        }:
            issues.append(
                "unsupported_asset_type"
            )

        if not (
            isinstance(asset.source_url, str)
            and asset.source_url.strip()
        ):
            issues.append(
                "source_url_missing"
            )

        if not (
            isinstance(asset.source_name, str)
            and asset.source_name.strip()
        ):
            issues.append(
                "source_name_missing"
            )

        if not asset.license_name:
            issues.append(
                "license_unknown"
            )

        if (
            asset.commercial_use_allowed
            is not True
        ):
            issues.append(
                "commercial_use_not_verified"
            )

        try:
            relevance = float(
                asset.relevance_score
            )
        except (
            TypeError,
            ValueError,
        ):
            relevance = 0.0

        if relevance < self.MIN_RELEVANCE_SCORE:
            issues.append(
                "asset_relevance_below_threshold"
            )

        if (
            asset.content_id is not None
            and asset.content_id != content_id
        ):
            issues.append(
                "content_id_mismatch"
            )

        return (
            not issues,
            issues,
        )

    def authorize(
        self,
        assets: list[MediaAsset],
        *,
        content_id: str,
    ) -> list[MediaAsset]:

        authorized: list[MediaAsset] = []
        errors: list[dict] = []

        for asset in assets:

            valid, issues = (
                self.validate_asset(
                    asset,
                    content_id=content_id,
                )
            )

            if valid:
                authorized.append(asset)
            else:
                errors.append(
                    {
                        "asset_id": asset.asset_id,
                        "issues": issues,
                    }
                )

        if errors:
            raise RuntimeError(
                "Media authorization failed: "
                f"{errors}"
            )

        if not authorized:
            raise RuntimeError(
                "No production-authorized media "
                "was collected."
            )

        return authorized
