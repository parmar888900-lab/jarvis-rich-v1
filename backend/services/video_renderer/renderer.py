"""
Video Renderer

Responsible for creating the final MP4.

MoviePy 2.x compatible.
"""

from pathlib import Path
from backend.services.video.media_asset import media_provenance_identity

from backend.services.runtime.runtime_config import RuntimeConfig
from backend.services.video_renderer.moviepy_runtime import (
    configure_moviepy_ffmpeg,
)

from moviepy import (
    AudioFileClip,
    CompositeVideoClip,
    ImageClip,
    VideoFileClip,
    concatenate_videoclips,
)

from backend.models.generated_content import GeneratedContent
from backend.services.storyboard.scene import Scene
from backend.services.image_generation.models import GeneratedImage
from backend.services.video.caption_aligner import CaptionAligner
from backend.services.video_renderer.subtitle_renderer import SubtitleRenderer


class VideoRenderer:

    WIDTH = 1080
    HEIGHT = 1920
    FPS = 30

    def __init__(
        self,
        runtime_config: RuntimeConfig | None = None,
    ):

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

        self.subtitle_renderer = (
            SubtitleRenderer()
        )

        self.caption_aligner = (
            CaptionAligner()
        )

    def _cover_image_clip(
        self,
        image_path: Path,
        duration: float,
        zoom: float = 1.0,
    ):
        """
        Preserve source aspect ratio while filling the
        vertical frame. Overscan is centered instead of
        stretching the source image.
        """

        clip = ImageClip(str(image_path))

        source_width, source_height = clip.size

        if source_width <= 0 or source_height <= 0:
            clip.close()
            raise RuntimeError(
                "Invalid source image dimensions."
            )

        cover_scale = max(
            self.WIDTH / float(source_width),
            self.HEIGHT / float(source_height),
        )

        scale = cover_scale * max(1.0, float(zoom))

        target_width = max(
            self.WIDTH,
            int(round(source_width * scale)),
        )

        target_height = max(
            self.HEIGHT,
            int(round(source_height * scale)),
        )

        return (
            clip
            .resized((target_width, target_height))
            .with_duration(max(0.05, float(duration)))
            .with_position(("center", "center"))
        )

    def _fit_visual(
        self,
        clip,
        duration: float,
    ):
        """
        Fit moving source video to the vertical output frame
        while preserving aspect ratio.

        Uses the same cover-and-center policy as authorized
        image rendering. The source remains moving video.
        """

        source_width, source_height = clip.size

        if source_width <= 0 or source_height <= 0:
            raise RuntimeError(
                "Invalid source video dimensions."
            )

        cover_scale = max(
            self.WIDTH / float(source_width),
            self.HEIGHT / float(source_height),
        )

        target_width = max(
            self.WIDTH,
            int(round(source_width * cover_scale)),
        )

        target_height = max(
            self.HEIGHT,
            int(round(source_height * cover_scale)),
        )

        return (
            clip
            .resized(
                (
                    target_width,
                    target_height,
                )
            )
            .with_duration(
                max(
                    0.05,
                    float(duration),
                )
            )
            .with_position(
                (
                    "center",
                    "center",
                )
            )
        )

    async def render(
        self,
        content: GeneratedContent,
        scenes: list[Scene],
        images: list[GeneratedImage],
        production_package: dict,
        visual_beats: list[dict] | None = None,
        beat_images: list[GeneratedImage] | None = None,
        beat_videos: list[dict] | None = None,
    ) -> dict:

        if not scenes:
            raise RuntimeError(
                "Storyboard contains no scenes."
            )

        if not images:
            raise RuntimeError(
                "Renderer received no authorized images."
            )

        if len(images) != len(scenes):
            raise RuntimeError(
                "Image/storyboard mismatch."
            )

        # Stage 2A deliberately keeps the existing rights-safe
        # one-authorized-image-per-story-stage acquisition rule.
        # The renderer creates a denser editorial timeline from
        # those authorized assets without requesting unverified
        # media.

        voice = production_package["voice"]

        audio_path = Path(
            voice["audio_path"]
        )

        if not audio_path.exists():
            raise FileNotFoundError(
                f"Audio not found: {audio_path}"
            )

        audio = AudioFileClip(
            str(audio_path)
        )

        audio_duration = audio.duration

        if audio_duration <= 0:
            audio.close()

            raise RuntimeError(
                "Narration has invalid duration."
            )

        image_clips = []
        subtitle_clips = []

        # RICH_V1_REAL_VIDEO_V6_1
        video_source_clips = []

        beat_video_lookup = {
            int(
                item.get(
                    "beat_index",
                    -1,
                )
            ): item
            for item in (beat_videos or [])
            if isinstance(
                item,
                dict,
            )
        }

        base_video = None
        final_video = None

        caption_mode = "whisper"

        try:

            ##################################################
            # Build synchronized image clips
            ##################################################

            # Stage 2B semantic editorial timeline.
            #
            # Preferred path:
            # one visual clip per semantic micro-beat.
            #
            # Fallback path:
            # Stage 2A 4/3/3/2 editorial rhythm using the four
            # already-authorized story-stage images.

            use_semantic_beats = bool(
                visual_beats
                and beat_images
                and len(visual_beats)
                == len(beat_images)
            )

            if use_semantic_beats:

                # BLOCK5_RENDERER_QA_BEGIN
                #
                # Independent last-line defense. Even if a future
                # pipeline refactor bypasses the upstream gate,
                # Stage2B will not render a sequence dominated by
                # repeated physical images.

                def block5_identity(image):
                    return media_provenance_identity(image)

                block5_paths = [block5_identity(image) for image in beat_images]

                block5_path_counts = {}

                for block5_path in block5_paths:
                    block5_path_counts[
                        block5_path
                    ] = (
                        block5_path_counts.get(
                            block5_path,
                            0,
                        )
                        + 1
                    )

                block5_renderer_distinct = len(
                    block5_path_counts
                )

                block5_renderer_run = 1
                block5_renderer_max_run = 1

                for block5_index in range(
                    1,
                    len(block5_paths),
                ):
                    if (
                        block5_paths[block5_index]
                        == block5_paths[
                            block5_index - 1
                        ]
                    ):
                        block5_renderer_run += 1
                        block5_renderer_max_run = max(
                            block5_renderer_max_run,
                            block5_renderer_run,
                        )
                    else:
                        block5_renderer_run = 1

                block5_renderer_share = (
                    max(
                        block5_path_counts.values()
                    )
                    / len(block5_paths)
                )

                if (
                    block5_renderer_distinct
                    < min(
                        4,
                        len(block5_paths),
                    )
                ):
                    raise RuntimeError(
                        "Stage2B renderer visual QA rejected "
                        "insufficient distinct imagery."
                    )

                if block5_renderer_max_run > 2:
                    raise RuntimeError(
                        "Stage2B renderer visual QA rejected "
                        "more than 2 consecutive identical "
                        "beat images."
                    )

                if (
                    len(block5_paths) >= 8
                    and block5_renderer_share > 0.42
                ):
                    raise RuntimeError(
                        "Stage2B renderer visual QA rejected "
                        "a dominant repeated beat image."
                    )

                # BLOCK5_RENDERER_QA_END

                raw_durations = []

                for beat in visual_beats:

                    try:
                        duration = float(
                            beat.get(
                                "target_duration",
                                2.5,
                            )
                        )
                    except (
                        TypeError,
                        ValueError,
                    ):
                        duration = 2.5

                    # Hook-biased pacing:
                    # first visual changes are deliberately
                    # quicker; later explanation/payoff beats
                    # are allowed slightly more breathing room.
                    beat_position = len(
                        raw_durations
                    )

                    if beat_position == 0:
                        pace_multiplier = 0.62
                    elif beat_position == 1:
                        pace_multiplier = 0.72
                    elif beat_position == 2:
                        pace_multiplier = 0.82
                    elif beat_position >= max(
                        0,
                        len(visual_beats) - 2,
                    ):
                        pace_multiplier = 1.12
                    else:
                        pace_multiplier = 1.0

                    duration *= pace_multiplier

                    raw_durations.append(
                        max(
                            0.65,
                            min(
                                duration,
                                3.5,
                            ),
                        )
                    )

                raw_total = sum(
                    raw_durations
                )

                if raw_total <= 0:
                    raw_total = float(
                        len(raw_durations)
                    )

                    raw_durations = [
                        1.0
                        for _ in raw_durations
                    ]

                scaled_durations = [
                    audio_duration
                    * duration
                    / raw_total
                    for duration in raw_durations
                ]

                for beat_index, (
                    beat,
                    image,
                    cut_duration,
                ) in enumerate(
                    zip(
                        visual_beats,
                        beat_images,
                        scaled_durations,
                    ),
                    start=1,
                ):

                    image_path = Path(
                        image.image_path
                    )

                    if not image_path.exists():
                        raise FileNotFoundError(
                            "Beat image not found: "
                            f"{image_path}"
                        )

                    # Controlled alternating reframes keep static
                    # licensed imagery alive without fabricating
                    # content or modifying its meaning.
                    # Restrained motion pattern:
                    # enough movement to prevent slideshow feel
                    # without turning every shot into an effect.
                    zoom_pattern = (
                        1.00,
                        1.025,
                        1.050,
                        1.015,
                        1.040,
                    )

                    zoom = zoom_pattern[
                        (beat_index - 1)
                        % len(zoom_pattern)
                    ]

                    # RICH_V1_REAL_VIDEO_V6_1
                    #
                    # Default remains the existing authorized
                    # image. A strict semantic video match can
                    # replace it for this beat.
                    clip = None

                    video_spec = beat_video_lookup.get(
                        beat_index
                    )

                    if video_spec is not None:

                        source_path = Path(
                            str(
                                video_spec.get(
                                    "source_path",
                                    "",
                                )
                            )
                        )

                        if source_path.exists():

                            source_video = None

                            try:

                                source_video = (
                                    VideoFileClip(
                                        str(
                                            source_path
                                        )
                                    )
                                )

                                video_source_clips.append(
                                    source_video
                                )

                                start_time = max(
                                    0.0,
                                    float(
                                        video_spec.get(
                                            "start_time",
                                            0.0,
                                        )
                                    ),
                                )

                                end_time = min(
                                    float(
                                        source_video.duration
                                    ),
                                    float(
                                        video_spec.get(
                                            "end_time",
                                            start_time
                                            + cut_duration,
                                        )
                                    ),
                                )

                                if (
                                    end_time
                                    > start_time
                                    + 0.05
                                ):

                                    moving_clip = (
                                        source_video
                                        .subclipped(
                                            start_time,
                                            end_time,
                                        )
                                        .without_audio()
                                    )

                                    available_duration = (
                                        float(
                                            moving_clip.duration
                                        )
                                    )

                                    if (
                                        available_duration
                                        >= cut_duration
                                    ):

                                        moving_clip = (
                                            moving_clip
                                            .subclipped(
                                                0.0,
                                                cut_duration,
                                            )
                                        )

                                        clip = (
                                            self._fit_visual(
                                                moving_clip,
                                                cut_duration,
                                            )
                                        )

                                    else:

                                        # Do not stretch/freeze a
                                        # short clip just to force
                                        # a match. Fall back to
                                        # the authorized image.
                                        clip = None

                            except Exception:

                                clip = None

                    if clip is None:

                        clip = self._cover_image_clip(
                            image_path=image_path,
                            duration=cut_duration,
                            zoom=zoom,
                        )

                    image_clips.append(
                        clip
                    )

            else:

                # Stage 2A fallback.
                cut_allocation = {
                    1: 4,
                    2: 3,
                    3: 3,
                    4: 2,
                }

                total_scene_duration = sum(
                    max(
                        float(scene.duration),
                        0.01,
                    )
                    for scene in scenes
                )

                for scene_index, (
                    scene,
                    image,
                ) in enumerate(
                    zip(
                        scenes,
                        images,
                    ),
                    start=1,
                ):

                    image_path = Path(
                        image.image_path
                    )

                    if not image_path.exists():
                        raise FileNotFoundError(
                            f"Image not found: {image_path}"
                        )

                    cuts = cut_allocation.get(
                        scene_index,
                        2,
                    )

                    scene_share = (
                        max(
                            float(scene.duration),
                            0.01,
                        )
                        / total_scene_duration
                    )

                    stage_duration = (
                        audio_duration
                        * scene_share
                    )

                    cut_duration = (
                        stage_duration
                        / cuts
                    )

                    for local_cut in range(cuts):

                        zoom = (
                            1.00
                            if local_cut % 3 == 0
                            else (
                                1.035
                                if local_cut % 3 == 1
                                else 1.065
                            )
                        )

                        clip = self._cover_image_clip(
                            image_path=image_path,
                            duration=cut_duration,
                            zoom=zoom,
                        )

                        image_clips.append(
                            clip
                        )

            ##################################################
            # Combine micro-shot editorial timeline
            ##################################################

            base_video = concatenate_videoclips(
                image_clips,
                method="compose",
            )

            ##################################################
            # Build speech-aligned subtitles
            ##################################################

            try:

                phrases = (
                    await self.caption_aligner
                    .align_phrases(
                        str(audio_path)
                    )
                )

                for phrase in phrases:

                    subtitle = (
                        self.subtitle_renderer
                        .create_clip(
                            text=phrase["text"],
                            start_time=phrase[
                                "start_time"
                            ],
                            end_time=phrase[
                                "end_time"
                            ],
                        )
                    )

                    subtitle_clips.append(
                        subtitle
                    )

            except Exception as exc:

                caption_mode = "fallback"

                print(
                    "Whisper caption alignment "
                    "failed. Using fallback "
                    "captions."
                )

                print(
                    f"Alignment error: {exc}"
                )

                ##################################################
                # Fallback proportional captions
                ##################################################

                for scene in scenes:

                    phrase_clips = (
                        self.subtitle_renderer
                        .create_phrase_clips(
                            text=scene.narration,
                            start_time=scene.start_time,
                            end_time=scene.end_time,
                        )
                    )

                    subtitle_clips.extend(
                        phrase_clips
                    )

            ##################################################
            # Composite images + subtitles
            ##################################################

            final_video = CompositeVideoClip(
                [
                    base_video,
                    *subtitle_clips,
                ],
                size=(
                    self.WIDTH,
                    self.HEIGHT,
                ),
            )

            final_video = (
                final_video
                .with_audio(audio)
                .with_duration(
                    audio_duration
                )
            )

            ##################################################
            # Safe filename
            ##################################################

            safe_name = "".join(
                c if c.isalnum() else "_"
                for c in content.title
            )[:60]

            output = (
                self.output_dir
                / f"{safe_name}.mp4"
            )

            ##################################################
            # Render
            ##################################################

            final_video.write_videofile(
                str(output),
                fps=self.FPS,
                codec="libx264",
                audio_codec="aac",
                logger=None,
            )

        finally:

            if final_video is not None:
                final_video.close()

            if base_video is not None:
                base_video.close()

            for subtitle in subtitle_clips:
                subtitle.close()

            for clip in image_clips:
                clip.close()

            # RICH_V1_REAL_VIDEO_V6_1
            for source_video in video_source_clips:
                try:
                    source_video.close()
                except Exception:
                    pass

            audio.close()

        return {
            "status": "success",
            "video_path": str(output),
            "title": content.title,
            "duration": audio_duration,
            "resolution": (
                f"{self.WIDTH}x{self.HEIGHT}"
            ),
            "fps": self.FPS,
            "captions": True,
            "caption_mode": caption_mode,
            "visual_engine": (
                "stage2b_semantic_microbeat"
                if use_semantic_beats
                else "stage2a_microshot_fallback"
            ),
            "visual_cut_count": len(image_clips),
            "story_stage_count": len(scenes),
            "average_visual_cut_seconds": round(
                audio_duration / max(1, len(image_clips)),
                3,
            ),
            "hook_visual_strategy": (
                "accelerated_first_three_beats"
                if use_semantic_beats
                else "stage2a_fallback"
            ),
            "semantic_beat_count": (
                len(visual_beats)
                if visual_beats
                else 0
            ),
            "semantic_media_enabled": (
                use_semantic_beats
            ),
            "editorial_pacing": (
                "hook_biased_dynamic"
                if use_semantic_beats
                else "stage2a_fallback"
            ),
            "caption_phrase_target_words": 3,
            "visual_framing": "aspect_preserving_cover",
        }
