import json
from dataclasses import replace
from pathlib import Path
import wave

from backend.services.runtime.runtime_config import RuntimeConfig
from backend.services.video.sound_design import OriginalSoundDesigner


def test_original_sound_design_is_deterministic_ducked_and_provenanced(tmp_path):
    narration = tmp_path / "narration.wav"
    with wave.open(str(narration), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(22_050)
        # One second of clear synthetic speech activity followed by silence.
        active = (b"\x00\x20" * 22_050)
        silent = (b"\x00\x00" * 22_050)
        handle.writeframes(active + silent)

    config = replace(
        RuntimeConfig.from_environment(),
        generated_dir=tmp_path / "generated",
    )
    designer = OriginalSoundDesigner(runtime_config=config)
    first = designer.generate(
        narration_path=str(narration),
        duration=2.0,
        cue_times=[0.0, 0.5, 1.0, 1.5],
    )
    second = designer.generate(
        narration_path=str(narration),
        duration=2.0,
        cue_times=[0.0, 0.5, 1.0, 1.5],
    )

    assert first["source_hash"] == second["source_hash"]
    assert first["narration_aware_ducking"] is True
    assert first["commercial_use_allowed"] is True
    assert first["license_name"] == "Original procedural audio"
    audio_path = Path(first["audio_path"])
    assert audio_path.exists()
    assert json.loads(audio_path.with_suffix(".json").read_text())["asset_id"]
    with wave.open(str(audio_path), "rb") as handle:
        assert handle.getnchannels() == 2
        assert handle.getframerate() == 44_100
