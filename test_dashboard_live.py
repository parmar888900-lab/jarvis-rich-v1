"""Owner command center serves benchmark-informed shell with protected live data."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.routes.dashboard import router as dashboard_router
from backend.routes.network import router as network_router
from scripts.run_dashboard import dashboard_config


def test_dashboard_shell_and_owner_only_stream(monkeypatch):
    monkeypatch.setenv("JARVIS_REMOTE_TOKEN", "test-owner-token")
    app = FastAPI()
    app.include_router(dashboard_router)
    app.include_router(network_router)
    with TestClient(app) as client:
        page = client.get("/dashboard")
        assert page.status_code == 200
        for part in ("JARVIS", "AI CORE", "TALK TO JARVIS", "STALE DATA",
                     "RECONNECTING", "YouTube network", "Human action required",
                     "viewport-fit=cover", "@media(max-width:760px)"):
            assert part in page.text
        assert "innerHTML" not in page.text
        assert client.get("/api/network/status").status_code == 401
        assert client.get("/api/network/events").status_code == 401
        assert client.get("/dashboard/manifest.webmanifest").json()["display"] == "standalone"


def test_lan_binding_requires_owner_token_and_tls(monkeypatch, tmp_path):
    monkeypatch.setenv("JARVIS_DASHBOARD_HOST", "0.0.0.0")
    monkeypatch.delenv("JARVIS_REMOTE_TOKEN", raising=False)
    with pytest.raises(RuntimeError, match="owner token"):
        dashboard_config()
    monkeypatch.setenv("JARVIS_REMOTE_TOKEN", "x" * 40)
    with pytest.raises(RuntimeError, match="TLS"):
        dashboard_config()
    cert = tmp_path / "cert.pem"
    key = tmp_path / "key.pem"
    cert.write_text("fixture")
    key.write_text("fixture")
    monkeypatch.setenv("JARVIS_DASHBOARD_CERT", str(cert))
    monkeypatch.setenv("JARVIS_DASHBOARD_KEY", str(key))
    assert dashboard_config()["ssl_certfile"] == str(cert)


def test_loopback_starts_without_lan_credentials(monkeypatch):
    monkeypatch.delenv("JARVIS_DASHBOARD_HOST", raising=False)
    monkeypatch.delenv("JARVIS_REMOTE_TOKEN", raising=False)
    assert dashboard_config()["host"] == "127.0.0.1"


def test_dashboard_script_can_import_backend_from_repo_root():
    import subprocess
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parent
    result = subprocess.run([sys.executable, "-c", "import runpy; runpy.run_path('scripts/run_dashboard.py')"],
                            cwd=root, capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
