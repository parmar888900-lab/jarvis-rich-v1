"""Local WAV playback for Jarvis voice responses."""

from __future__ import annotations

import wave
from pathlib import Path

import numpy as np
import sounddevice as sd


class AudioPlayer:
    """Play PCM WAV files through a selected output device."""

    def __init__(
        self,
        *,
        device: int | str | None = None,
    ) -> None:
        self.device = device

    def validate_device(self) -> dict:
        info = sd.query_devices(
            self.device,
            kind="output",
        )

        channels = int(
            info.get(
                "max_output_channels",
                0,
            )
        )

        if channels <= 0:
            raise RuntimeError(
                "Selected audio device has "
                "no output channels."
            )

        return {
            "name": info.get(
                "name"
            ),
            "max_output_channels": channels,
            "default_sample_rate": int(
                info.get(
                    "default_samplerate",
                    0,
                )
            ),
        }

    def play(
        self,
        audio_path: str | Path,
    ) -> dict:
        path = Path(
            audio_path
        )

        if not path.exists():
            raise FileNotFoundError(
                f"Audio file not found: {path}"
            )

        if (
            path.suffix.lower()
            != ".wav"
        ):
            raise ValueError(
                "AudioPlayer supports WAV files only."
            )

        device = self.validate_device()

        with wave.open(
            str(path),
            "rb",
        ) as wav:
            channels = wav.getnchannels()
            sample_width = wav.getsampwidth()
            sample_rate = wav.getframerate()
            frame_count = wav.getnframes()

            if channels <= 0:
                raise RuntimeError(
                    "Invalid WAV channel count."
                )

            if sample_rate <= 0:
                raise RuntimeError(
                    "Invalid WAV sample rate."
                )

            if sample_width != 2:
                raise RuntimeError(
                    "AudioPlayer currently requires "
                    "16-bit PCM WAV audio."
                )

            raw = wav.readframes(
                frame_count
            )

        audio = np.frombuffer(
            raw,
            dtype=np.int16,
        )

        if channels > 1:
            audio = audio.reshape(
                -1,
                channels,
            )

        sd.play(
            audio,
            samplerate=sample_rate,
            device=self.device,
            blocking=True,
        )

        duration = (
            frame_count
            / float(sample_rate)
        )

        return {
            "status": "success",
            "audio_path": str(path),
            "duration": duration,
            "sample_rate": sample_rate,
            "channels": channels,
            "device": device,
        }
