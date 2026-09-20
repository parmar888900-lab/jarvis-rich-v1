"""Profile-driven multi-shot renderer for Jarvis Rich V1."""

from __future__ import annotations
import hashlib
import subprocess

from pathlib import Path

from moviepy import (
    AudioFileClip,
    CompositeVideoClip,
    ImageClip,
    VideoFileClip,
    concatenate_videoclips,
)

from backend.services.runtime.runtime_config import RuntimeConfig
from backend.services.video.media_asset import MediaAsset
from backend.services.video.reference_profiles import (
    RichFormatProfile,
)
from backend.services.video_renderer.moviepy_runtime import (
    configure_moviepy_ffmpeg,
)


class RichMultiShotRenderer:
    """
    Render fast vertical Shorts from multiple real media assets.

    V1 responsibilities:
        - profile-driven shot timing
        - video + image inputs
        - 9:16 crop/reframe
        - mild per-shot zoom variation
        - narration/music attachment
        - 1080x1920 output
    """

    def __init__(
        self,
        runtime_config: RuntimeConfig | None = None,
    ) -> None:

        config = (
            runtime_config
            if runtime_config is not None
            else RuntimeConfig.from_environment()
        )

        self.ffmpeg_executable = (
            configure_moviepy_ffmpeg(
                config.ffmpeg_executable
            )
        )

        self.output_dir = (
            Path(config.generated_dir)
            / "videos"
        )

        self.output_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.normalized_video_dir = (
            Path(config.generated_dir)
            / "normalized_video"
        )

        self.normalized_video_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

    async def render(
        self,
        *,
        title: str,
        assets: list[MediaAsset],
        profile: RichFormatProfile,
        narration_audio_path: str | None = None,
        music_audio_path: str | None = None,
    ) -> dict:

        if not assets:
            raise RuntimeError(
                "RichMultiShotRenderer received no assets."
            )

        target_duration = float(
            profile.target_duration
        )

        ####################################################
        # Determine timeline duration.
        #
        # If narration exists, narration controls the final
        # timeline for narrated formats.
        ####################################################

        narration = None
        music = None

        if narration_audio_path:

            narration_path = Path(
                narration_audio_path
            )

            if not narration_path.exists():
                raise FileNotFoundError(
                    narration_path
                )

            narration = AudioFileClip(
                str(narration_path)
            )

            if (
                profile.narration_enabled
                and narration.duration > 0
            ):
                target_duration = min(
                    max(
                        narration.duration,
                        profile.min_duration,
                    ),
                    profile.max_duration,
                )

        if music_audio_path:

            music_path = Path(
                music_audio_path
            )

            if not music_path.exists():
                raise FileNotFoundError(
                    music_path
                )

            music = AudioFileClip(
                str(music_path)
            )

        ####################################################
        # Build the visual sequence.
        ####################################################

        shot_clips = []

        try:

            current_time = 0.0
            asset_index = 0
            shot_index = 0

            while current_time < target_duration:

                asset = assets[
                    asset_index
                    % len(assets)
                ]

                remaining = (
                    target_duration
                    - current_time
                )

                duration = self._shot_duration(
                    profile=profile,
                    shot_index=shot_index,
                    remaining=remaining,
                )

                clip = self._build_asset_clip(
                    asset=asset,
                    duration=duration,
                    profile=profile,
                    shot_index=shot_index,
                )

                shot_clips.append(
                    clip
                )

                current_time += duration
                asset_index += 1
                shot_index += 1

            if not shot_clips:
                raise RuntimeError(
                    "Renderer produced no visual shots."
                )

            base = concatenate_videoclips(
                shot_clips,
                method="compose",
            )

            base = base.with_duration(
                target_duration
            )

            ################################################
            # Audio
            ################################################

            final = base

            if narration is not None:

                narration = narration.subclipped(
                    0,
                    min(
                        narration.duration,
                        target_duration,
                    ),
                )

                final = final.with_audio(
                    narration
                )

            elif (
                music is not None
                and profile.music_enabled
            ):

                music_duration = min(
                    music.duration,
                    target_duration,
                )

                music = music.subclipped(
                    0,
                    music_duration,
                )

                final = final.with_audio(
                    music
                )

            ################################################
            # Safe filename
            ################################################

            safe_name = "".join(
                c if c.isalnum()
                else "_"
                for c in title
            )[:70]

            output = (
                self.output_dir
                / (
                    f"{safe_name}_"
                    f"{profile.format_name}.mp4"
                )
            )

            ################################################
            # Render
            ################################################

            final.write_videofile(
                str(output),
                fps=profile.fps,
                codec="libx264",
                audio_codec="aac",
                logger=None,
            )

            final.close()
            base.close()

            return {
                "status": "success",
                "video_path": str(output),
                "duration": target_duration,
                "format_name": (
                    profile.format_name
                ),
                "benchmark_reference": (
                    profile.benchmark_reference
                ),
                "shot_count": len(
                    shot_clips
                ),
                "resolution": (
                    f"{profile.width}"
                    f"x{profile.height}"
                ),
                "fps": profile.fps,
            }

        finally:

            for clip in shot_clips:

                try:
                    clip.close()
                except Exception:
                    pass

            if narration is not None:

                try:
                    narration.close()
                except Exception:
                    pass

            if music is not None:

                try:
                    music.close()
                except Exception:
                    pass

    def _normalize_video_for_moviepy(
        self,
        source_path: Path,
    ) -> Path:
        """
        Normalize third-party video containers before MoviePy reads
        them.

        This removes timecode/data streams and provider metadata that
        can confuse MoviePy's FFmpeg parser, while caching the result
        so repeated renders do not transcode the same asset again.
        """

        stat = source_path.stat()

        identity = (
            f"{source_path.resolve()}|"
            f"{stat.st_size}|"
            f"{stat.st_mtime_ns}"
        )

        digest = hashlib.sha1(
            identity.encode(
                "utf-8"
            )
        ).hexdigest()[:16]

        output = (
            self.normalized_video_dir
            / f"{digest}.mp4"
        )

        if (
            output.exists()
            and output.stat().st_size > 0
        ):
            return output

        command = [
            self.ffmpeg_executable,
            "-y",

            "-i",
            str(source_path),

            # Keep only the primary video stream.
            "-map",
            "0:v:0",

            # Explicitly remove non-video streams.
            "-an",
            "-sn",
            "-dn",

            # Remove timecode/provider metadata.
            "-map_metadata",
            "-1",

            "-metadata",
            "timecode=",

            # Stable MoviePy-friendly encoding.
            "-c:v",
            "libx264",

            "-preset",
            "veryfast",

            "-crf",
            "18",

            "-pix_fmt",
            "yuv420p",

            "-movflags",
            "+faststart",

            str(output),
        ]

        completed = subprocess.run(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
            timeout=180,
        )

        if (
            completed.returncode != 0
            or not output.exists()
            or output.stat().st_size <= 0
        ):
            raise RuntimeError(
                "FFmpeg video normalization failed for "
                f"{source_path}: "
                f"{completed.stderr[-1500:]}"
            )

        return output

    def _build_asset_clip(
        self,
        *,
        asset: MediaAsset,
        duration: float,
        profile: RichFormatProfile,
        shot_index: int,
    ):

        source_path = Path(
            asset.file_path
        )

        if not source_path.exists():
            raise FileNotFoundError(
                source_path
            )

        if asset.asset_type == "video":

            normalized_path = (
                self._normalize_video_for_moviepy(
                    source_path
                )
            )

            source = VideoFileClip(
                str(normalized_path)
            )

            if source.duration <= 0:
                source.close()

                raise RuntimeError(
                    "Video asset has invalid duration: "
                    f"{source_path}"
                )

            usable_duration = min(
                duration,
                source.duration,
            )

            ################################################
            # Avoid always starting at frame zero.
            ################################################

            max_start = max(
                0.0,
                source.duration
                - usable_duration,
            )

            if max_start > 0:

                fraction = (
                    (
                        shot_index * 0.37
                    )
                    % 1.0
                )

                start = (
                    max_start
                    * fraction
                )

            else:
                start = 0.0

            clip = source.subclipped(
                start,
                start + usable_duration,
            )

        elif asset.asset_type == "image":

            clip = (
                ImageClip(
                    str(source_path)
                )
                .with_duration(
                    duration
                )
            )

        else:

            raise ValueError(
                "Unsupported media type: "
                f"{asset.asset_type}"
            )

        ####################################################
        # 9:16 crop/reframe.
        ####################################################

        scale = max(
            profile.width / clip.w,
            profile.height / clip.h,
        )

        clip = clip.resized(
            scale
        )

        ####################################################
        # Mild zoom variation.
        ####################################################

        if (
            profile.zoom_enabled
            and shot_index % 3 == 1
        ):
            clip = clip.resized(
                1.035
            )

        elif (
            profile.zoom_enabled
            and shot_index % 3 == 2
        ):
            clip = clip.resized(
                1.06
            )

        clip = clip.cropped(
            x_center=clip.w / 2,
            y_center=clip.h / 2,
            width=profile.width,
            height=profile.height,
        )

        return clip.with_duration(
            duration
        )

    @staticmethod
    def _shot_duration(
        *,
        profile: RichFormatProfile,
        shot_index: int,
        remaining: float,
    ) -> float:

        ####################################################
        # Deterministic rhythmic variation.
        ####################################################

        pattern = (
            0.82,
            1.00,
            1.18,
            0.92,
            1.08,
        )

        factor = pattern[
            shot_index
            % len(pattern)
        ]

        duration = (
            profile.target_shot_duration
            * factor
        )

        duration = max(
            profile.min_shot_duration,
            min(
                duration,
                profile.max_shot_duration,
            ),
        )

        return min(
            duration,
            remaining,
        )
