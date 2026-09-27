from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.services.video import voice_generator as module


@pytest.mark.asyncio
async def test_piper_uses_process_tree_watchdog_and_bounded_stdin(monkeypatch, tmp_path):
    generator = module.VoiceGenerator.__new__(module.VoiceGenerator)
    generator.piper_executable = Path("piper")
    generator.model_path = Path("british-male.onnx")
    generator.output_dir = tmp_path
    calls = []

    def bounded(command, **kwargs):
        calls.append((command, kwargs))
        Path(command[-1]).write_bytes(b"RIFF test audio")
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(module, "run_bounded", bounded)
    output = tmp_path / "greeting.wav"
    await generator._run_piper("Welcome, Mr. Parmar.", output)
    assert output.exists()
    assert calls[0][1]["stdin_data"] == b"Welcome, Mr. Parmar."
    assert 0 < calls[0][1]["timeout_seconds"] <= 900
    assert calls[0][1]["stage"] == "piper-tts"
