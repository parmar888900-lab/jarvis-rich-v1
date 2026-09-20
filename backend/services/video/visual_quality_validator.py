"""Objective visual-quality validation for Rich V1 media."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter, ImageStat

from backend.services.video.media_asset import MediaAsset


class VisualQualityValidator:
    """
    Detect media that is technically valid but visually unsuitable.

    This gate measures objective frame quality only. It does not
    decide semantic relevance; VisualSemanticValidator handles that.
    """

    # Provisional calibration thresholds.
    # We will tune these from real Jarvis audit results before
    # enabling automatic rejection.
    MIN_BRIGHTNESS = 22.0
    MAX_BRIGHTNESS = 238.0
    MAX_DARK_RATIO = 0.82
    MAX_BRIGHT_RATIO = 0.90
    MIN_CONTRAST = 12.0
    MIN_EDGE_ACTIVITY = 8.0

    VIDEO_SAMPLE_POSITIONS = (
        0.20,
        0.50,
        0.80,
    )

    def __init__(
        self,
        *,
        ffmpeg_binary: str | None = None,
    ) -> None:

        self.ffmpeg_binary = (
            ffmpeg_binary
            or shutil.which("ffmpeg")
            or "ffmpeg"
        )

    def validate(
        self,
        *,
        asset: MediaAsset,
    ) -> dict:

        frame_paths = self._sample_frames(
            asset
        )

        if not frame_paths:
            return {
                "valid": False,
                "reason": "no_quality_frames",
                "frames": [],
            }

        frame_results = []

        try:

            for frame_path in frame_paths:

                result = self._analyze_frame(
                    frame_path
                )

                frame_results.append(
                    result
                )

        finally:

            if asset.asset_type == "video":

                for frame_path in frame_paths:

                    try:
                        frame_path.unlink(
                            missing_ok=True
                        )
                    except OSError:
                        pass

        usable_count = sum(
            1
            for item in frame_results
            if item["valid"]
        )

        ####################################################
        # Images require their only frame to pass.
        # Videos pass if at least 2 of 3 sampled frames pass.
        ####################################################

        required = (
            1
            if asset.asset_type == "image"
            else min(
                2,
                len(frame_results),
            )
        )

        valid = (
            usable_count >= required
        )

        averages = self._averages(
            frame_results
        )

        return {
            "valid": valid,
            "reason": (
                "visual_quality_ok"
                if valid
                else "visual_quality_failed"
            ),
            "usable_frames": usable_count,
            "required_frames": required,
            "averages": averages,
            "frames": frame_results,
        }

    def _analyze_frame(
        self,
        path: Path,
    ) -> dict:

        try:

            with Image.open(
                path
            ) as image:

                image = image.convert(
                    "RGB"
                )

                # Downsample for predictable QA cost.
                image.thumbnail(
                    (720, 720),
                    Image.Resampling.LANCZOS,
                )

                gray = image.convert(
                    "L"
                )

                array = np.asarray(
                    gray,
                    dtype=np.float32,
                )

                if array.size == 0:
                    return self._failed_frame(
                        "empty_frame"
                    )

                brightness = float(
                    array.mean()
                )

                contrast = float(
                    array.std()
                )

                dark_ratio = float(
                    np.mean(
                        array <= 18.0
                    )
                )

                bright_ratio = float(
                    np.mean(
                        array >= 245.0
                    )
                )

                ################################################
                # Edge activity:
                # low value usually means blur, blankness,
                # extreme darkness, or low-information imagery.
                ################################################

                edges = gray.filter(
                    ImageFilter.FIND_EDGES
                )

                edge_array = np.asarray(
                    edges,
                    dtype=np.float32,
                )

                edge_activity = float(
                    edge_array.std()
                )

                issues = []

                ################################################
                # Dark imagery may still be visually usable.
                #
                # Title cards, logos, night shots, and high-
                # contrast cinematic frames can be intentionally
                # dark while still containing strong structure.
                ################################################

                dark_but_informative = (
                    contrast >= 25.0
                    and edge_activity >= 25.0
                )

                if (
                    brightness
                    < self.MIN_BRIGHTNESS
                    and not dark_but_informative
                ):
                    issues.append(
                        "too_dark"
                    )

                if (
                    brightness
                    > self.MAX_BRIGHTNESS
                ):
                    issues.append(
                        "too_bright"
                    )

                if (
                    dark_ratio
                    > self.MAX_DARK_RATIO
                    and not dark_but_informative
                ):
                    issues.append(
                        "mostly_black"
                    )

                if (
                    bright_ratio
                    > self.MAX_BRIGHT_RATIO
                ):
                    issues.append(
                        "mostly_white"
                    )

                if (
                    contrast
                    < self.MIN_CONTRAST
                ):
                    issues.append(
                        "low_contrast"
                    )

                if (
                    edge_activity
                    < self.MIN_EDGE_ACTIVITY
                ):
                    issues.append(
                        "low_visual_information"
                    )

                return {
                    "valid": not issues,
                    "brightness": round(
                        brightness,
                        2,
                    ),
                    "contrast": round(
                        contrast,
                        2,
                    ),
                    "dark_ratio": round(
                        dark_ratio,
                        4,
                    ),
                    "bright_ratio": round(
                        bright_ratio,
                        4,
                    ),
                    "edge_activity": round(
                        edge_activity,
                        2,
                    ),
                    "issues": issues,
                }

        except Exception as exc:

            return self._failed_frame(
                "frame_analysis_error",
                detail=str(exc),
            )

    def _sample_frames(
        self,
        asset: MediaAsset,
    ) -> list[Path]:

        source = Path(
            asset.file_path
        )

        if not source.exists():
            return []

        if asset.asset_type == "image":
            return [
                source
            ]

        if asset.asset_type != "video":
            return []

        duration = float(
            asset.duration
            or 0.0
        )

        ####################################################
        # If provider duration is unavailable, use fixed
        # early/middle-ish timestamps.
        ####################################################

        if duration > 1.5:

            timestamps = [
                max(
                    0.15,
                    duration * position,
                )
                for position
                in self.VIDEO_SAMPLE_POSITIONS
            ]

        else:

            timestamps = [
                0.25,
                0.75,
                1.25,
            ]

        output_paths = []

        for index, timestamp in enumerate(
            timestamps,
            start=1,
        ):

            output = (
                Path(
                    tempfile.gettempdir()
                )
                / (
                    "jarvis_quality_"
                    f"{asset.asset_id}_"
                    f"{index}.jpg"
                )
            )

            command = [
                self.ffmpeg_binary,
                "-y",
                "-loglevel",
                "error",
                "-ss",
                str(
                    round(
                        timestamp,
                        3,
                    )
                ),
                "-i",
                str(source),
                "-frames:v",
                "1",
                "-q:v",
                "3",
                str(output),
            ]

            try:

                completed = subprocess.run(
                    command,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                    timeout=45,
                )

            except (
                OSError,
                subprocess.TimeoutExpired,
            ):
                continue

            if (
                completed.returncode == 0
                and output.exists()
            ):
                output_paths.append(
                    output
                )

        return output_paths

    @staticmethod
    def _averages(
        results: list[dict],
    ) -> dict:

        valid_metrics = [
            item
            for item in results
            if (
                "brightness" in item
                and "contrast" in item
            )
        ]

        if not valid_metrics:
            return {}

        keys = (
            "brightness",
            "contrast",
            "dark_ratio",
            "bright_ratio",
            "edge_activity",
        )

        return {
            key: round(
                sum(
                    float(item[key])
                    for item
                    in valid_metrics
                )
                / len(valid_metrics),
                3,
            )
            for key in keys
        }

    @staticmethod
    def _failed_frame(
        reason: str,
        *,
        detail: str = "",
    ) -> dict:

        return {
            "valid": False,
            "issues": [
                reason
            ],
            "detail": detail,
        }

