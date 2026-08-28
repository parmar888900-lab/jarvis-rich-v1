"""
Local voice generation for Jarvis using Piper TTS.
"""

import asyncio
import wave
from pathlib import Path


class VoiceGenerator:

    def __init__(self):

        self.output_dir = Path("generated/audio")

        self.output_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.model_path = Path(
            "models/piper/"
            "en_GB-northern_english_male-medium.onnx"
        )

        self.piper_executable = Path(
            "venv/Scripts/piper.exe"
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

        if not self.model_path.exists():
            raise FileNotFoundError(
                f"Piper model not found: {self.model_path}"
            )

        if not self.piper_executable.exists():
            raise FileNotFoundError(
                f"Piper executable not found: "
                f"{self.piper_executable}"
            )

        output_file = (
            self.output_dir
            / f"{filename}.wav"
        )

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

        stdout, stderr = await process.communicate(
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

            return frames / float(frame_rate)
