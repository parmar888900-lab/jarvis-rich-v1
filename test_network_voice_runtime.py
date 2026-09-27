import asyncio
from types import SimpleNamespace

import pytest

from backend.services.voice import voice_runtime


@pytest.mark.asyncio
async def test_voice_uses_default_microphone_and_independent_recovery(monkeypatch, tmp_path):
    monkeypatch.setattr(voice_runtime, "VOICE_DIR", tmp_path)
    devices = []

    class Capture:
        def __init__(self, *, device=None):
            devices.append(device)

    calls = []

    class Assistant:
        def __init__(self, audio_capture):
            assert isinstance(audio_capture, Capture)

        async def interact_once(self, *args, **kwargs):
            calls.append(1)
            if len(calls) == 1:
                raise RuntimeError("temporary microphone failure")
            raise asyncio.CancelledError

    waits = []

    async def wait(seconds):
        waits.append(seconds)

    monkeypatch.setattr(voice_runtime, "AudioCapture", Capture)
    monkeypatch.setattr(voice_runtime, "VoiceAssistant", Assistant)
    monkeypatch.setattr(voice_runtime.asyncio, "sleep", wait)
    with pytest.raises(asyncio.CancelledError):
        await voice_runtime.run_voice_runtime()
    assert devices == [None]
    assert calls == [1, 1]
    assert waits == [2]


@pytest.mark.asyncio
async def test_voice_runtime_does_not_log_spoken_secrets(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(voice_runtime, "VOICE_DIR", tmp_path)
    async def no_db():
        return None
    monkeypatch.setattr(voice_runtime, "init_db", no_db)
    class Capture:
        pass
    class Assistant:
        def __init__(self, audio_capture):
            pass
        async def interact_once(self, *args, **kwargs):
            if not hasattr(self, "done"):
                self.done = True
                return SimpleNamespace(assistant_result=SimpleNamespace(
                    status="completed", transcript="private spoken credential"))
            raise asyncio.CancelledError
    monkeypatch.setattr(voice_runtime, "AudioCapture", Capture)
    monkeypatch.setattr(voice_runtime, "VoiceAssistant", Assistant)
    with pytest.raises(asyncio.CancelledError):
        await voice_runtime.run_voice_runtime()
    assert "private spoken credential" not in capsys.readouterr().out
