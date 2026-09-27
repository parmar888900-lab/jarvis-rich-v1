#!/usr/bin/env python3
"""Owner dashboard server, loopback by default, TLS mandatory for LAN binding."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import uvicorn

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def dashboard_config() -> dict:
    host = os.environ.get("JARVIS_DASHBOARD_HOST", "127.0.0.1").strip()
    port = int(os.environ.get("JARVIS_DASHBOARD_PORT", "8765"))
    certificate = os.environ.get("JARVIS_DASHBOARD_CERT", "").strip()
    key = os.environ.get("JARVIS_DASHBOARD_KEY", "").strip()
    if not 1 <= port <= 65535:
        raise ValueError("Dashboard port must be 1..65535")
    if host not in {"127.0.0.1", "localhost", "::1"}:
        if len(os.environ.get("JARVIS_REMOTE_TOKEN", "").strip()) < 32:
            raise RuntimeError("LAN dashboard requires a 32+ character owner token")
        if not certificate or not key or not Path(certificate).is_file() or not Path(key).is_file():
            raise RuntimeError("LAN dashboard requires configured TLS certificate and key files")
    options = {"host": host, "port": port, "access_log": False}
    if certificate and key:
        options.update(ssl_certfile=certificate, ssl_keyfile=key)
    return options


if __name__ == "__main__":
    os.environ["JARVIS_PUBLIC_PUBLISH_ENABLED"] = "false"
    os.environ.setdefault("DEBUG", "false")
    uvicorn.run("backend.remote_app:app", **dashboard_config())
