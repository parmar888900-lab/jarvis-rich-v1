"""
Video Renderer

Responsible for creating the final MP4.

MoviePy 2.x compatible.
"""

from pathlib import Path

from backend.services.runtime.runtime_config import RuntimeConfig
from backend.services.video_renderer.moviepy_runtime import (
    configure_moviepy_ffmpeg,
)

from moviepy import (
    AudioFileClip,
    CompositeVideoClip,
    ImageClip,
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

    async def render(
        self,
        content: GeneratedContent,
        scenes: list[Scene],
        images: list[GeneratedImage],
        production_package: dict,
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

        base_video = None
        final_video = None

        caption_mode = "whisper"

        try:

            ##################################################
            # Build synchronized image clips
            ##################################################

            # Stage 2A editorial timeline.
            #
            # Four narration stages remain the semantic backbone,
            # while visuals cut several times inside each stage.
            # This removes the old four-static-shot presentation.
            #
            # Allocation:
            #   stage 1 / hook       -> 4 cuts
            #   stage 2 / context    -> 3 cuts
            #   stage 3 / escalation -> 3 cuts
            #   stage 4 / payoff     -> 2 cuts
            #
            # Only authorized images supplied by the pipeline are
            # used. No licensing or evidence gate is bypassed.

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

            for scene_index, (scene, image) in enumerate(
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

                # Scene durations come from the narration
                # storyboard. Scale them to the final voice length
                # so the visual timeline always covers the audio.
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

                    # Alternate subtle scale values. This produces
                    # editorial motion while retaining the exact
                    # authorized source image.
                    zoom = (
                        1.00
                        if local_cut % 3 == 0
                        else (
                            1.035
                            if local_cut % 3 == 1
                            else 1.065
                        )
                    )

                    target_width = int(
                        self.WIDTH
                        * zoom
                    )

                    target_height = int(
                        self.HEIGHT
                        * zoom
                    )

                    clip = (
                        ImageClip(
                            str(image_path)
                        )
                        .resized(
                            (
                                target_width,
                                target_height,
                            )
                        )
                        .with_duration(
                            cut_duration
                        )
                    )

                    # Center oversized zoomed frames.
                    if (
                        target_width != self.WIDTH
                        or target_height != self.HEIGHT
                    ):
                        clip = clip.with_position(
                            ("center", "center")
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
            "visual_engine": "stage2a_microshot",
            "visual_cut_count": len(image_clips),
            "story_stage_count": len(scenes),
        }
