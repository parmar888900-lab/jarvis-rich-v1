"""The static Safari client must stop old streams after owner reconnect."""
from pathlib import Path
import re
import shutil
import subprocess


def test_dashboard_reconnect_generation_and_voice_error_state(tmp_path):
    html = (Path(__file__).parent / "backend/dashboard/index.html").read_text()
    assert "epoch!==state.epoch" in html
    assert "state.epoch++" in html
    assert "Piper response unavailable" in html
    assert "state.voice='IDLE'" in html
    if shutil.which("node"):
        script = re.search(r"<script>(.*?)</script>", html, re.S).group(1)
        source = tmp_path / "dashboard.js"
        source.write_text(script)
        subprocess.run(["node", "--check", str(source)], check=True, timeout=10)
