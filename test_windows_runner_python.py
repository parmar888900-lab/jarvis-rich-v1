"""The commissioned Windows venv takes priority over an obsolete .venv."""

from pathlib import Path


def test_all_windows_runners_prefer_known_live_venv_and_keep_qa_private():
    root = Path(__file__).parent / "scripts" / "windows"
    for filename in ("run_jarvis_network.cmd", "run_jarvis_voice.cmd",
                     "run_jarvis_dashboard.cmd"):
        text = (root / filename).read_text(encoding="utf-8")
        preferred = 'set "JARVIS_PYTHON=venv\\Scripts\\python.exe"'
        fallback = 'set "JARVIS_PYTHON=.venv\\Scripts\\python.exe"'
        assert text.index(preferred) < text.index(fallback)
        assert "set JARVIS_PUBLIC_PUBLISH_ENABLED=false" in text
        assert "timeout /t 15 /nobreak" in text
    lan = (root / "configure_dashboard_lan.ps1").read_text(encoding="utf-8")
    assert lan.index("Join-Path $repo 'venv\\Scripts\\python.exe'") < lan.index(
        "Join-Path $repo '.venv\\Scripts\\python.exe'")
