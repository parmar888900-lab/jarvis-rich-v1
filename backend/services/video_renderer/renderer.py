"""
Video Renderer

Responsible for creating the final MP4.

MoviePy 2.x compatible.
"""

from pathlib import Path

from moviepy import (
    AudioFileClip,
    ImageClip,
    concatenate_videoclips,
)

from backend.models.generated_content import GeneratedContent
from backend.services.storyboard.scene import Scene
from backend.services.image_generation.models import GeneratedImage


class VideoRenderer:

    WIDTH = 1080
    HEIGHT = 1920
    FPS = 30

    def __init__(self):

        self.output_dir = Path("generated/videos")

        self.output_dir.mkdir(
            parents=True,
            exist_ok=True,
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

        if len(images) != len(scenes):
            raise RuntimeError(
                "Image/storyboard mismatch."
            )

        voice = production_package["voice"]

        audio_path = Path(
            voice["audio_path"]
        )

        if not audio_path.exists():
            raise FileNotFoundError(
                f"Audio not found: {audio_path}"
            )

        ##################################################
        # Load narration
        ##################################################

        audio = AudioFileClip(
            str(audio_path)
        )

        audio_duration = audio.duration

        if audio_duration <= 0:
            audio.close()

            raise RuntimeError(
                "Narration has invalid duration."
            )

        ##################################################
        # Synchronize scenes to narration
        ##################################################

        scene_duration = (
            audio_duration / len(scenes)
        )

        clips = []

        try:

            ##################################################
            # Build image clips
            ##################################################

            for scene, image in zip(
                scenes,
                images,
            ):

                image_path = Path(
                    image.image_path
                )

                if not image_path.exists():
                    raise FileNotFoundError(
                        f"Image not found: {image_path}"
                    )

                clip = (
                    ImageClip(str(image_path))
                    .resized(
                        (
                            self.WIDTH,
                            self.HEIGHT,
                        )
                    )
                    .with_duration(
                        scene_duration
                    )
                )

                clips.append(clip)

            ##################################################
            # Combine clips
            ##################################################

            video = concatenate_videoclips(
                clips,
                method="compose",
            )

            video = video.with_audio(
                audio
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

            video.write_videofile(
                str(output),
                fps=self.FPS,
                codec="libx264",
                audio_codec="aac",
                logger=None,
            )

            video.close()

        finally:

            audio.close()

            for clip in clips:
                clip.close()

        ##################################################
        # Return
        ##################################################

        return {
            "status": "success",
            "video_path": str(output),
            "title": content.title,
            "duration": audio_duration,
            "resolution": (
                f"{self.WIDTH}x{self.HEIGHT}"
            ),
            "fps": self.FPS,
        }
