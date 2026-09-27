"""Atomic, non-secret local service heartbeat for command-center observation."""

import json
import os
from datetime import datetime, timezone
from pathlib import Path


def write_heartbeat(path: Path, *, state: str, detail: str | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"state": state, "detail": detail,
               "observed_at": datetime.now(timezone.utc).isoformat(),
               "pid": os.getpid()}
    temporary = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    temporary.write_text(json.dumps(payload), encoding="utf-8")
    temporary.replace(path)


def read_heartbeat(path: Path, *, max_age_seconds: int) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        observed = datetime.fromisoformat(data["observed_at"])
        age = (datetime.now(timezone.utc) - observed).total_seconds()
        return {"state": data.get("state"), "detail": data.get("detail"),
                "observed_at": data["observed_at"], "fresh": 0 <= age < max_age_seconds}
    except (OSError, ValueError, KeyError, TypeError):
        return {"state": "UNAVAILABLE", "detail": None, "observed_at": None,
                "fresh": False}
