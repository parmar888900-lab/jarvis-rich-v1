"""
Builds a complete production package.

Everything required to recreate the video is stored
inside one folder.

Package Structure

generated/packages/<video>/

    metadata.json
    trend.json
    script.txt
    voice.json
    scenes.json
    images.json
    captions.srt

    narration.wav

    images/
        scene_001.png
        scene_002.png
        ...
"""

import json
import shutil
from dataclasses import asdict
from pathlib import Path

from backend.models.generated_content import GeneratedContent
from backend.services.storyboard.scene import Scene
from backend.services.video.voice_generator import VoiceGenerator


class ProductionPackageBuilder:

    def __init__(self):

        self.voice = VoiceGenerator()

        self.base_dir = Path("generated/packages")
        self.base_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

    async def build(
        self,
        content: GeneratedContent,
        scenes: list[Scene],
        images: list,
        trend: dict | None = None,
    ) -> dict:

        ####################################################
        # Safe folder name
        ####################################################

        safe_name = "".join(
            c if c.isalnum() else "_"
            for c in content.title
        )[:60]

        package_dir = self.base_dir / safe_name

        package_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        ####################################################
        # Images folder
        ####################################################

        images_dir = package_dir / "images"

        images_dir.mkdir(
            exist_ok=True,
        )

        ####################################################
        # Script
        ####################################################

        script = content.full_script

        ####################################################
        # Voice Generation
        ####################################################

        voice = await self.voice.generate_scenes(
            scenes,
            filename=safe_name,
        )

        ####################################################
        # Copy narration into package
        ####################################################

        audio_source = Path(
            voice["audio_path"]
        )

        audio_destination = (
            package_dir / audio_source.name
        )

        if audio_source.exists():

            shutil.copy2(
                audio_source,
                audio_destination,
            )

        voice["audio_path"] = str(
            audio_destination
        )

        ####################################################
        # Copy images
        ####################################################

        image_manifest = []

        for index, image in enumerate(images):

            source = Path(
                image.image_path
            )

            destination = (
                images_dir
                / f"scene_{index+1:03d}{source.suffix}"
            )

            if source.exists():

                shutil.copy2(
                    source,
                    destination,
                )

            image_manifest.append(
                {
                    "scene": index + 1,
                    "provider": image.provider,
                    "prompt": image.prompt,
                    "image_path": str(destination),
                    "width": image.width,
                    "height": image.height,
                }
            )

        ####################################################
        # Metadata
        ####################################################

        duration = voice["duration"]

        metadata = {

            "title": content.title,

            "hashtags": content.hashtags,

            "scene_count": len(scenes),

            "duration": duration,

            "created_by": "Jarvis Rich V1",

            "metadata": content.metadata,

        }

        ####################################################
        # Save metadata
        ####################################################

        (
            package_dir / "metadata.json"
        ).write_text(

            json.dumps(
                metadata,
                indent=4,
            ),

            encoding="utf-8",
        )

        ####################################################
        # Save trend (optional)
        ####################################################

        if trend is not None:

            (
                package_dir / "trend.json"
            ).write_text(

                json.dumps(
                    trend,
                    indent=4,
                ),

                encoding="utf-8",
            )

        ####################################################
        # Save script
        ####################################################

        (
            package_dir / "script.txt"
        ).write_text(

            script,

            encoding="utf-8",
        )

        ####################################################
        # Save voice metadata
        ####################################################

        (
            package_dir / "voice.json"
        ).write_text(

            json.dumps(
                voice,
                indent=4,
            ),

            encoding="utf-8",
        )

        ####################################################
        # Save storyboard
        ####################################################

        (
            package_dir / "scenes.json"
        ).write_text(

            json.dumps(

                [
                    asdict(scene)
                    for scene in scenes
                ],

                indent=4,

            ),

            encoding="utf-8",
        )

        ####################################################
        # Save image manifest
        ####################################################

        (
            package_dir / "images.json"
        ).write_text(

            json.dumps(
                image_manifest,
                indent=4,
            ),

            encoding="utf-8",
        )

        ####################################################
        # Empty captions (V1)
        ####################################################

        (
            package_dir / "captions.srt"
        ).write_text(
            self._build_srt(scenes),
            encoding="utf-8",
        )

        ####################################################
        # Return package
        ####################################################

        return {

            "package_dir": str(package_dir),

            "metadata": metadata,

            "voice": voice,

            "images": image_manifest,

            "scene_count": len(scenes),

            "duration": duration,

            "script": script,

        }



    @staticmethod
    def _format_srt_time(
        seconds: float,
    ) -> str:

        milliseconds = round(
            seconds * 1000
        )

        hours = (
            milliseconds // 3_600_000
        )

        milliseconds %= 3_600_000

        minutes = (
            milliseconds // 60_000
        )

        milliseconds %= 60_000

        secs = (
            milliseconds // 1000
        )

        millis = (
            milliseconds % 1000
        )

        return (
            f"{hours:02d}:"
            f"{minutes:02d}:"
            f"{secs:02d},"
            f"{millis:03d}"
        )

    @classmethod
    def _build_srt(
        cls,
        scenes: list[Scene],
    ) -> str:

        blocks = []

        for index, scene in enumerate(
            scenes,
            start=1,
        ):

            start = cls._format_srt_time(
                scene.start_time
            )

            end = cls._format_srt_time(
                scene.end_time
            )

            blocks.append(
                f"{index}\n"
                f"{start} --> {end}\n"
                f"{scene.narration.strip()}"
            )

        return "\n\n".join(
            blocks
        ) + "\n"
