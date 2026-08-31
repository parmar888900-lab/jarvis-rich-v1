"""Microphone audio capture for the Jarvis voice assistant."""

from __future__ import annotations

from pathlib import Path
import wave

import numpy as np
import sounddevice as sd


class AudioCapture:
    """Capture synchronized mono WAV recordings from a microphone."""

    def __init__(
        self,
        *,
        device: int | str | None = None,
        sample_rate: int | None = None,
        channels: int = 1,
        dtype: str = "int16",
        warmup_seconds: float = 0.5,
    ) -> None:
        if sample_rate is not None and sample_rate <= 0:
            raise ValueError(
                "Sample rate must be positive when configured."
            )

        if channels != 1:
            raise ValueError(
                "Voice capture currently requires mono audio."
            )

        if dtype != "int16":
            raise ValueError(
                "Voice capture currently requires int16 audio."
            )

        if warmup_seconds < 0:
            raise ValueError(
                "Warm-up duration cannot be negative."
            )

        self.device = device
        self.sample_rate = (
            int(sample_rate)
            if sample_rate is not None
            else None
        )
        self.channels = channels
        self.dtype = dtype
        self.warmup_seconds = float(
            warmup_seconds
        )

    def get_device_info(self) -> dict:
        """Return validated input-device metadata."""

        info = sd.query_devices(
            self.device,
            "input",
        )

        max_channels = int(
            info.get(
                "max_input_channels",
                0,
            )
        )

        if max_channels < self.channels:
            raise RuntimeError(
                "Configured device does not provide "
                "the required input channels."
            )

        native_rate = int(
            round(
                float(
                    info.get(
                        "default_samplerate",
                        0.0,
                    )
                )
            )
        )

        if native_rate <= 0:
            raise RuntimeError(
                "Configured microphone reported "
                "an invalid sample rate."
            )

        capture_rate = (
            self.sample_rate
            if self.sample_rate is not None
            else native_rate
        )

        sd.check_input_settings(
            device=self.device,
            channels=self.channels,
            samplerate=capture_rate,
            dtype=self.dtype,
        )

        return {
            "name": str(
                info.get(
                    "name",
                    "",
                )
            ),
            "max_input_channels": max_channels,
            "native_sample_rate": native_rate,
            "capture_sample_rate": capture_rate,
        }

    def validate_device(self) -> dict:
        """Compatibility alias for device validation."""

        return self.get_device_info()

    def record(
        self,
        output_path: str | Path,
        *,
        duration_seconds: float,
        on_ready=None,
    ) -> dict:
        """Record one synchronized fixed-duration utterance."""

        try:
            duration = float(
                duration_seconds
            )
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "Recording duration must be numeric."
            ) from exc

        if duration <= 0:
            raise ValueError(
                "Recording duration must be positive."
            )

        path = Path(output_path)

        if path.suffix.lower() != ".wav":
            raise ValueError(
                "Voice recording output must be a WAV file."
            )

        info = self.get_device_info()

        rate = int(
            info["capture_sample_rate"]
        )

        frame_count = int(
            round(
                duration * rate
            )
        )

        if frame_count <= 0:
            raise ValueError(
                "Recording duration produced no audio frames."
            )

        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        overflowed = False

        with sd.InputStream(
            device=self.device,
            samplerate=rate,
            channels=self.channels,
            dtype=self.dtype,
        ) as stream:

            warmup_frames = int(
                round(
                    self.warmup_seconds
                    * rate
                )
            )

            if warmup_frames > 0:
                _, warmup_overflow = stream.read(
                    warmup_frames
                )

                overflowed = bool(
                    warmup_overflow
                )

            if on_ready is not None:
                on_ready()

            audio, recording_overflow = stream.read(
                frame_count
            )

            overflowed = (
                overflowed
                or bool(
                    recording_overflow
                )
            )

        audio = np.asarray(
            audio,
            dtype=np.int16,
        )

        expected_shape = (
            frame_count,
            self.channels,
        )

        if audio.shape != expected_shape:
            raise RuntimeError(
                "Microphone returned an unexpected "
                f"audio shape: {audio.shape}"
            )

        if audio.size == 0:
            raise RuntimeError(
                "Microphone returned no audio samples."
            )

        with wave.open(
            str(path),
            "wb",
        ) as wav:
            wav.setnchannels(
                self.channels
            )
            wav.setsampwidth(2)
            wav.setframerate(rate)
            wav.writeframes(
                audio.tobytes()
            )

        if not path.exists():
            raise RuntimeError(
                "Microphone recording was not written."
            )

        return {
            "status": "success",
            "audio_path": str(path),
            "duration_seconds": duration,
            "sample_rate": rate,
            "native_sample_rate": int(
                info["native_sample_rate"]
            ),
            "channels": self.channels,
            "dtype": self.dtype,
            "frames": frame_count,
            "device": self.device,
            "device_name": info["name"],
            "overflowed": overflowed,
        }
