"""Shot/clip indexing for Jarvis Rich V1 source footage."""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path

from backend.services.video.media_asset import MediaAsset


@dataclass(slots=True)
class IndexedSourceClip:
    clip_id: str
    asset_id: str
    source_path: str
    source_name: str

    start_time: float
    end_time: float
    duration: float

    preview_path: str

    width: int | None = None
    height: int | None = None

    def to_dict(self) -> dict:
        return asdict(self)


class SourceClipIndexer:
    """
    Convert source videos into short selectable visual moments.

    The indexer does not render the final Short.
    It identifies candidate shot windows that ClipMatcher can later
    rank against narration/visual beats.
    """

    MIN_CLIP_DURATION = 1.0
    TARGET_CLIP_DURATION = 2.0
    MAX_CLIP_DURATION = 3.2

    SCENE_THRESHOLD = 0.30

    MAX_CLIPS_PER_ASSET = 40

    def __init__(
        self,
        *,
        ffmpeg_binary: str | None = None,
        ffprobe_binary: str | None = None,
        output_root: str | Path = (
            "generated/clip_index"
        ),
    ) -> None:

        self.ffmpeg = (
            ffmpeg_binary
            or shutil.which("ffmpeg")
            or "ffmpeg"
        )

        self.ffprobe = (
            ffprobe_binary
            or shutil.which("ffprobe")
            or "ffprobe"
        )

        self.output_root = Path(
            output_root
        )

        self.output_root.mkdir(
            parents=True,
            exist_ok=True,
        )

    def index_assets(
        self,
        *,
        assets: list[MediaAsset],
        content_id: str,
    ) -> list[IndexedSourceClip]:

        output: list[
            IndexedSourceClip
        ] = []

        for asset in assets:

            if asset.asset_type != "video":
                continue

            output.extend(
                self.index_asset(
                    asset=asset,
                    content_id=content_id,
                )
            )

        return output

    def index_asset(
        self,
        *,
        asset: MediaAsset,
        content_id: str,
    ) -> list[IndexedSourceClip]:

        source = Path(
            asset.file_path
        )

        if not source.exists():
            return []

        duration = self._duration(
            source
        )

        if duration <= 0:
            return []

        boundaries = self._scene_boundaries(
            source
        )

        windows = self._build_windows(
            duration=duration,
            boundaries=boundaries,
        )

        output_dir = (
            self.output_root
            / content_id
            / asset.asset_id
        )

        output_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        clips: list[
            IndexedSourceClip
        ] = []

        for index, (
            start,
            end,
        ) in enumerate(
            windows[
                :self.MAX_CLIPS_PER_ASSET
            ],
            start=1,
        ):

            preview = (
                output_dir
                / f"clip_{index:03d}.jpg"
            )

            midpoint = (
                start
                + (
                    end - start
                )
                / 2.0
            )

            if not self._extract_frame(
                source=source,
                timestamp=midpoint,
                output=preview,
            ):
                continue

            clip_id = (
                f"{asset.asset_id}_"
                f"{index:03d}"
            )

            clips.append(
                IndexedSourceClip(
                    clip_id=clip_id,
                    asset_id=asset.asset_id,
                    source_path=str(source),
                    source_name=(
                        asset.source_name
                    ),
                    start_time=round(
                        start,
                        3,
                    ),
                    end_time=round(
                        end,
                        3,
                    ),
                    duration=round(
                        end - start,
                        3,
                    ),
                    preview_path=str(
                        preview
                    ),
                    width=asset.width,
                    height=asset.height,
                )
            )

        return clips

    def _duration(
        self,
        source: Path,
    ) -> float:

        command = [
            self.ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            (
                "default="
                "noprint_wrappers=1:"
                "nokey=1"
            ),
            str(source),
        ]

        try:

            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=False,
                timeout=30,
            )

            if completed.returncode != 0:
                return 0.0

            return float(
                completed.stdout.strip()
            )

        except Exception:
            return 0.0

    def _scene_boundaries(
        self,
        source: Path,
    ) -> list[float]:

        ####################################################
        # FFmpeg prints scene-change timestamps through
        # showinfo. We only use these as candidate boundaries.
        ####################################################

        filter_value = (
            "select="
            f"'gt(scene,{self.SCENE_THRESHOLD})',"
            "showinfo"
        )

        command = [
            self.ffmpeg,
            "-hide_banner",
            "-i",
            str(source),
            "-vf",
            filter_value,
            "-an",
            "-f",
            "null",
            "-",
        ]

        try:

            completed = subprocess.run(
                command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
                timeout=180,
            )

        except Exception:
            return []

        matches = re.findall(
            r"pts_time:([0-9]+(?:\.[0-9]+)?)",
            completed.stderr,
        )

        values = []

        for item in matches:

            try:
                value = float(
                    item
                )
            except ValueError:
                continue

            if value > 0:
                values.append(
                    value
                )

        return sorted(
            set(values)
        )

    def _build_windows(
        self,
        *,
        duration: float,
        boundaries: list[float],
    ) -> list[tuple[float, float]]:

        ####################################################
        # Prefer real scene boundaries.
        ####################################################

        points = [
            0.0,
            *[
                value
                for value in boundaries
                if (
                    0.0 < value < duration
                )
            ],
            duration,
        ]

        windows: list[
            tuple[float, float]
        ] = []

        for index in range(
            len(points) - 1
        ):

            start = points[index]
            stop = points[index + 1]

            scene_duration = (
                stop - start
            )

            if (
                scene_duration
                < self.MIN_CLIP_DURATION
            ):
                continue

            current = start

            while current < stop:

                remaining = (
                    stop - current
                )

                if (
                    remaining
                    < self.MIN_CLIP_DURATION
                ):
                    break

                clip_duration = min(
                    self.TARGET_CLIP_DURATION,
                    remaining,
                    self.MAX_CLIP_DURATION,
                )

                end = min(
                    current
                    + clip_duration,
                    stop,
                )

                if (
                    end - current
                    >= self.MIN_CLIP_DURATION
                ):
                    windows.append(
                        (
                            current,
                            end,
                        )
                    )

                current = end

        ####################################################
        # Some videos contain very few detectable cuts.
        # Fall back to uniform windows rather than producing
        # an empty index.
        ####################################################

        if len(windows) < 4:

            windows = []

            current = 0.0

            while (
                current
                < duration
                and len(windows)
                < self.MAX_CLIPS_PER_ASSET
            ):

                end = min(
                    current
                    + self.TARGET_CLIP_DURATION,
                    duration,
                )

                if (
                    end - current
                    < self.MIN_CLIP_DURATION
                ):
                    break

                windows.append(
                    (
                        current,
                        end,
                    )
                )

                current = end

        return windows

    def _extract_frame(
        self,
        *,
        source: Path,
        timestamp: float,
        output: Path,
    ) -> bool:

        command = [
            self.ffmpeg,
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

        except Exception:
            return False

        return (
            completed.returncode == 0
            and output.exists()
        )
