import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.routes.remote import transcribe_remote_audio


def test_remote_whisper_uses_tree_watchdog_and_cleans_result(tmp_path):
    audio = tmp_path / "command.webm"
    audio.write_bytes(b"test")
    seen = {}

    def runner(command, **kwargs):
        seen.update(kwargs)
        Path(command[3]).write_text(json.dumps({"status": "success", "text": "Jarvis"}))
        return SimpleNamespace(returncode=0)

    assert transcribe_remote_audio(audio, runner=runner)["text"] == "Jarvis"
    assert seen["timeout_seconds"] == 180
    assert seen["stage"] == "remote-whisper"
    assert audio.exists() and not audio.with_suffix(".webm.json").exists()


def test_failed_remote_whisper_is_recoverable(tmp_path):
    audio = tmp_path / "command.webm"
    audio.write_bytes(b"test")

    def runner(_command, **_kwargs):
        raise TimeoutError("bounded")

    with pytest.raises(TimeoutError):
        transcribe_remote_audio(audio, runner=runner)
    assert audio.exists()
