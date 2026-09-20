"""
Local voice generation for Jarvis using Piper TTS.
"""

import asyncio
import shutil
import wave
from pathlib import Path

from backend.services.storyboard.scene import Scene
from backend.services.runtime.runtime_config import RuntimeConfig


class VoiceGenerator:

    def __init__(
        self,
        runtime_config: RuntimeConfig | None = None,
    ):

        config = (
            runtime_config
            if runtime_config is not None
            else RuntimeConfig.from_environment()
        )

        self.output_dir = (
            Path(config.generated_dir)
            / "audio"
        )

        self.output_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.model_path = Path(
            config.piper_model_path
        )

        self.piper_executable = Path(
            config.piper_executable
        )

    async def generate(
        self,
        script: str,
        filename: str = "voice",
    ) -> dict:

        if not script.strip():
            raise ValueError(
                "VoiceGenerator received an empty script."
            )

        self._validate_piper()

        output_file = (
            self.output_dir
            / f"{filename}.wav"
        )

        await self._run_piper(
            script=script,
            output_file=output_file,
        )

        duration = self._get_duration(
            output_file
        )

        return {
            "status": "success",
            "audio_path": str(output_file),
            "duration": duration,
            "provider": "piper",
            "script": script,
        }

    async def generate_scenes(
        self,
        scenes: list[Scene],
        filename: str = "narration",
    ) -> dict:

        if not scenes:
            raise ValueError(
                "VoiceGenerator received no scenes."
            )

        self._validate_piper()

        scene_audio = []

        current_time = 0.0

        for index, scene in enumerate(
            scenes,
            start=1,
        ):

            narration = scene.narration.strip()

            if not narration:
                raise ValueError(
                    f"Scene {index} has empty narration."
                )

            scene_file = (
                self.output_dir
                / f"{filename}_scene_{index:03d}.wav"
            )

            await self._run_piper(
                script=narration,
                output_file=scene_file,
            )

            duration = self._get_duration(
                scene_file
            )

            scene.start_time = current_time
            scene.duration = duration
            scene.end_time = (
                current_time + duration
            )

            current_time = scene.end_time

            scene_audio.append(
                {
                    "scene": index,
                    "audio_path": str(scene_file),
                    "duration": duration,
                    "start_time": scene.start_time,
                    "end_time": scene.end_time,
                    "narration": narration,
                }
            )

        output_file = (
            self.output_dir
            / f"{filename}.wav"
        )

        self._concatenate_wav_files(
            [
                Path(item["audio_path"])
                for item in scene_audio
            ],
            output_file,
        )

        total_duration = self._get_duration(
            output_file
        )

        return {
            "status": "success",
            "audio_path": str(output_file),
            "duration": total_duration,
            "provider": "piper",
            "scenes": scene_audio,
            "script": "\n".join(
                scene.narration
                for scene in scenes
            ),
        }

    async def _run_piper(
        self,
        script: str,
        output_file: Path,
    ) -> None:

        process = await asyncio.create_subprocess_exec(
            str(self.piper_executable),
            "-m",
            str(self.model_path),
            "-f",
            str(output_file),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        _, stderr = await process.communicate(
            input=script.encode("utf-8")
        )

        if process.returncode != 0:

            error_message = stderr.decode(
                "utf-8",
                errors="replace",
            )

            raise RuntimeError(
                "Piper voice generation failed: "
                f"{error_message}"
            )

        if not output_file.exists():
            raise RuntimeError(
                "Piper completed but no WAV file "
                "was created."
            )

    def _validate_piper(self) -> None:

        if not self.model_path.exists():
            raise FileNotFoundError(
                f"Piper model not found: "
                f"{self.model_path}"
            )

        if self.piper_executable.is_file():
            return

        resolved = shutil.which(
            str(self.piper_executable)
        )

        if resolved is None:
            raise FileNotFoundError(
                f"Piper executable not found: "
                f"{self.piper_executable}"
            )

    @staticmethod
    def _concatenate_wav_files(
        input_files: list[Path],
        output_file: Path,
    ) -> None:

        if not input_files:
            raise ValueError(
                "No WAV files provided."
            )

        with wave.open(
            str(input_files[0]),
            "rb",
        ) as first:

            channels = first.getnchannels()
            sample_width = first.getsampwidth()
            frame_rate = first.getframerate()
            compression_type = first.getcomptype()
            compression_name = first.getcompname()

        with wave.open(
            str(output_file),
            "wb",
        ) as output:

            output.setnchannels(
                channels
            )

            output.setsampwidth(
                sample_width
            )

            output.setframerate(
                frame_rate
            )

            output.setcomptype(
                compression_type,
                compression_name,
            )

            for input_file in input_files:

                with wave.open(
                    str(input_file),
                    "rb",
                ) as source:

                    if (
                        source.getnchannels()
                        != channels
                        or source.getsampwidth()
                        != sample_width
                        or source.getframerate()
                        != frame_rate
                    ):
                        raise RuntimeError(
                            "Scene WAV format mismatch."
                        )

                    output.writeframes(
                        source.readframes(
                            source.getnframes()
                        )
                    )

    @staticmethod
    def _get_duration(
        audio_path: Path,
    ) -> float:

        with wave.open(
            str(audio_path),
            "rb",
        ) as wav:

            frames = wav.getnframes()
            frame_rate = wav.getframerate()

            if frame_rate <= 0:
                raise RuntimeError(
                    "Invalid WAV frame rate."
                )

            return frames / float(
                frame_rate
            )
