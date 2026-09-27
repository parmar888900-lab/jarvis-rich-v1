from pathlib import Path
import pytest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.routes.remote import router
from backend.routes import remote
from backend.services.video.voice_generator import VoiceGenerator


def test_owner_only_manual_piper_reply_and_cleanup(tmp_path, monkeypatch):
    monkeypatch.setenv("JARVIS_REMOTE_TOKEN", "voice-owner-token")
    paths = []

    async def generate(self, text, filename):
        assert text == "Welcome, Mr. Parmar."
        path = tmp_path / f"{filename}.wav"
        path.write_bytes(b"RIFFpiper-test")
        paths.append(path)
        return {"status": "success", "audio_path": str(path)}

    monkeypatch.setattr(VoiceGenerator, "generate", generate)
    app = FastAPI()
    app.include_router(router)
    with TestClient(app) as client:
        body = {"text": "Welcome, Mr. Parmar."}
        assert client.post("/remote/speech", json=body).status_code == 401
        response = client.post("/remote/speech", json=body, headers={
            "Authorization": "Bearer voice-owner-token"})
        assert response.status_code == 200
        assert response.content == b"RIFFpiper-test"
    assert paths and not paths[0].exists()


@pytest.mark.asyncio
async def test_manual_voice_routes_special_greeting_and_real_command(monkeypatch):
    remote.voice_formatter._home_greeting_index = 0
    first = await remote._route_manual_voice("Jarvis, wake up — Daddy’s home")
    second = await remote._route_manual_voice("Jarvis wake up, Daddy's home")
    assert first["message"] == "Welcome, sir."
    assert second["message"] == "Welcome, Mr. Parmar."
    seen = []

    async def route(command):
        seen.append(command)
        return {"status": "completed", "command": command}

    monkeypatch.setattr(remote, "_execute_command_text", route)
    await remote._route_manual_voice("Jarvis, how many videos are rendering?")
    await remote._route_manual_voice("How many videos are rendering?")
    assert seen == ["how many videos are rendering?", "How many videos are rendering?"]
