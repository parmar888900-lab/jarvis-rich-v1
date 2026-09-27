from datetime import datetime, timedelta, timezone
import json

from backend.services.network.heartbeat import read_heartbeat, write_heartbeat
from backend.services.network.supervisor import NetworkSupervisor


def test_atomic_heartbeat_and_stale_service(tmp_path):
    path = tmp_path / "state" / "voice.json"
    assert read_heartbeat(path, max_age_seconds=30)["state"] == "UNAVAILABLE"
    write_heartbeat(path, state="WAKE_LISTENING")
    assert read_heartbeat(path, max_age_seconds=30)["fresh"] is True
    data = json.loads(path.read_text())
    data["observed_at"] = (datetime.now(timezone.utc) - timedelta(minutes=2)).isoformat()
    path.write_text(json.dumps(data))
    assert read_heartbeat(path, max_age_seconds=30)["fresh"] is False


def test_child_log_rotation_preserves_three_backups(tmp_path):
    path = tmp_path / "worker.log"
    for value in ("first", "second", "third", "fourth"):
        path.write_text(value)
        NetworkSupervisor._rotate_log(path, max_bytes=1)
    assert [((tmp_path / f"worker.log.{i}").read_text()) for i in (1, 2, 3)] == [
        "fourth", "third", "second"]
