"""Deterministic, rights-safe sound design for Rich V1 Shorts."""

from __future__ import annotations

from array import array
import hashlib
import json
import math
from pathlib import Path
import wave

from backend.services.runtime.runtime_config import RuntimeConfig


class OriginalSoundDesigner:
    """Create a subtle original bed that automatically ducks under speech."""

    SAMPLE_RATE = 44_100
    BASE_LEVEL = 0.024
    DUCKED_LEVEL = 0.34
    SPEECH_RMS_THRESHOLD = 0.012

    def __init__(self, runtime_config: RuntimeConfig | None = None) -> None:
        config = runtime_config or RuntimeConfig.from_environment()
        self.output_dir = Path(config.generated_dir) / "audio" / "sound_design"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate(
        self,
        *,
        narration_path: str,
        duration: float,
        cue_times: list[float],
    ) -> dict:
        narration = Path(narration_path)
        if not narration.exists():
            raise FileNotFoundError(narration)

        safe_duration = max(0.1, float(duration))
        normalized_cues = sorted({
            round(max(0.0, min(safe_duration, float(value))), 3)
            for value in cue_times
        })
        digest = hashlib.sha256(
            narration.read_bytes()
            + json.dumps(
                [round(safe_duration, 3), normalized_cues],
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()[:16]
        output = self.output_dir / f"original_science_bed_{digest}.wav"
        manifest_path = output.with_suffix(".json")

        accent_cues = self._accent_cues(normalized_cues)
        if not output.exists():
            speech_rms = self._speech_rms(narration)
            frames = self._render_frames(
                duration=safe_duration,
                speech_rms=speech_rms,
                accent_cues=accent_cues,
            )
            with wave.open(str(output), "wb") as handle:
                handle.setnchannels(2)
                handle.setsampwidth(2)
                handle.setframerate(self.SAMPLE_RATE)
                handle.writeframes(frames.tobytes())

        manifest = {
            "enabled": True,
            "asset_id": f"jarvis-original-{digest}",
            "audio_path": str(output),
            "provider": "Jarvis Original Sound Design",
            "creator": "Jarvis Rich V1",
            "license_name": "Original procedural audio",
            "usage_basis": "Generated locally for this production",
            "commercial_use_allowed": True,
            "source_hash": hashlib.sha256(output.read_bytes()).hexdigest(),
            "narration_aware_ducking": True,
            "ducked_gain": self.DUCKED_LEVEL,
            "accent_cues": accent_cues,
            "sample_rate": self.SAMPLE_RATE,
            "channels": 2,
        }
        manifest_path.write_text(
            json.dumps(manifest, indent=2),
            encoding="utf-8",
        )
        return manifest

    @staticmethod
    def _accent_cues(cue_times: list[float]) -> list[float]:
        if not cue_times:
            return [0.0]
        selected = [cue_times[0]]
        for index in (3, 7, len(cue_times) - 2):
            if 0 <= index < len(cue_times):
                selected.append(cue_times[index])
        return sorted(set(selected))

    @staticmethod
    def _speech_rms(path: Path, window_seconds: float = 0.02) -> list[float]:
        with wave.open(str(path), "rb") as handle:
            channels = handle.getnchannels()
            sample_width = handle.getsampwidth()
            sample_rate = handle.getframerate()
            raw = handle.readframes(handle.getnframes())
        if sample_width != 2:
            return []
        samples = array("h")
        samples.frombytes(raw)
        window = max(1, int(sample_rate * window_seconds) * channels)
        output = []
        for start in range(0, len(samples), window):
            values = samples[start : start + window]
            if not values:
                break
            mean_square = sum(float(value) ** 2 for value in values) / len(values)
            output.append(math.sqrt(mean_square) / 32768.0)
        return output

    def _render_frames(
        self,
        *,
        duration: float,
        speech_rms: list[float],
        accent_cues: list[float],
    ) -> array:
        total = int(math.ceil(duration * self.SAMPLE_RATE))
        frames = array("h")
        duck_gain = 1.0
        for index in range(total):
            time_value = index / self.SAMPLE_RATE
            rms_index = min(
                len(speech_rms) - 1,
                max(0, int(time_value / 0.02)),
            ) if speech_rms else -1
            speech_active = (
                rms_index >= 0
                and speech_rms[rms_index] >= self.SPEECH_RMS_THRESHOLD
            )
            target_gain = self.DUCKED_LEVEL if speech_active else 1.0
            duck_gain += (target_gain - duck_gain) * 0.0012

            fade = min(1.0, time_value / 0.8, (duration - time_value) / 0.8)
            pad = (
                math.sin(2.0 * math.pi * 55.0 * time_value)
                + 0.55 * math.sin(2.0 * math.pi * 82.5 * time_value + 0.7)
                + 0.28 * math.sin(2.0 * math.pi * 110.0 * time_value + 1.4)
            ) / 1.83
            slow_motion = 0.78 + 0.22 * math.sin(
                2.0 * math.pi * 0.075 * time_value
            )
            value = self.BASE_LEVEL * duck_gain * fade * slow_motion * pad

            for cue in accent_cues:
                elapsed = time_value - cue
                if 0.0 <= elapsed <= 0.32:
                    value += (
                        0.030
                        * math.exp(-11.0 * elapsed)
                        * math.sin(2.0 * math.pi * 68.0 * elapsed)
                    )

            left = max(-1.0, min(1.0, value))
            right = max(-1.0, min(1.0, value * 0.94))
            frames.append(int(left * 32767.0))
            frames.append(int(right * 32767.0))
        return frames
