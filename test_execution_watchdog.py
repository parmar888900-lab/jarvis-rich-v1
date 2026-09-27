import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

import pytest

from backend.services.runtime.execution_watchdog import (
    ExecutionTimeoutError,
    ExecutionWatchdogError,
    run_bounded,
)


def _run(code, **kwargs):
    return run_bounded([sys.executable, "-c", code], stage="test-stage", **kwargs)


def _process_is_running(pid):
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes
        api = ctypes.WinDLL("kernel32", use_last_error=True)
        api.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        api.OpenProcess.restype = wintypes.HANDLE
        api.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        api.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = api.OpenProcess(0x1000, False, pid)
        if not handle:
            return False
        try:
            code = wintypes.DWORD()
            return bool(api.GetExitCodeProcess(handle, ctypes.byref(code))) and code.value == 259
        finally:
            api.CloseHandle(handle)
    stat = Path(f"/proc/{pid}/stat")
    if stat.exists():
        # Zombies are terminated; their reaping belongs to the system's init.
        return stat.read_text().split(")", 1)[1].split()[0] != "Z"
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False


def test_success_failure_and_append_only_child_logs(tmp_path):
    log = tmp_path / "stage.log"
    log.write_text("earlier checkpoint\n")
    events = []
    result = _run("print('completed output')", timeout_seconds=5, log_path=log, on_event=events.append)
    assert result.status == "completed"
    assert result.returncode == 0
    assert log.read_text() == "earlier checkpoint\ncompleted output\n"
    assert [event["status"] for event in events] == ["started", "completed"]
    failed = _run("raise SystemExit(7)", timeout_seconds=5, on_event=events.append)
    assert (failed.status, failed.returncode) == ("failed", 7)


def test_bounded_stdin_for_piper_style_workload(tmp_path):
    output = tmp_path / "speech.txt"
    secret_script = b"Welcome, Mr. Parmar."
    result = _run(f"import sys; from pathlib import Path; Path({str(output)!r}).write_bytes(sys.stdin.buffer.read())",
                  timeout_seconds=5, stdin_data=secret_script,
                  on_event=lambda event: None)
    assert result.returncode == 0
    assert output.read_bytes() == secret_script


@pytest.mark.parametrize("bad", [0, -1, float("inf"), float("nan"), -float("inf")])
def test_rejects_nonfinite_or_nonpositive_deadlines(bad):
    with pytest.raises(ValueError, match="timeout_seconds"):
        _run("pass", timeout_seconds=bad)


def test_invalid_heartbeat_grace_label_and_command_fail_before_spawn():
    for extra in ({"heartbeat_seconds": float("inf")}, {"terminate_grace_seconds": -1}):
        with pytest.raises(ValueError):
            _run("pass", timeout_seconds=5, **extra)
    with pytest.raises(ValueError, match="stage"):
        run_bounded([sys.executable], stage="unsafe\nlabel", timeout_seconds=5)
    with pytest.raises(ValueError, match="command"):
        run_bounded("shell command", stage="test", timeout_seconds=5)


def test_deadline_kills_child_tree_and_preserves_partial_work(tmp_path):
    child_pid = tmp_path / "child.pid"
    partial = tmp_path / "partial.mp4"
    code = (
        "import subprocess, sys, time; from pathlib import Path; "
        "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)']); "
        f"Path({str(child_pid)!r}).write_text(str(child.pid)); "
        f"Path({str(partial)!r}).write_bytes(b'valid-partial-checkpoint'); "
        "time.sleep(60)"
    )
    events = []
    started = time.monotonic()
    with pytest.raises(ExecutionTimeoutError) as caught:
        _run(code, timeout_seconds=0.8, heartbeat_seconds=0.1,
             terminate_grace_seconds=0.1, on_event=events.append)
    assert time.monotonic() - started < 4
    assert caught.value.result.status == "timed_out"
    assert "running" in [event["status"] for event in events]
    assert events[-1]["status"] == "timed_out"
    assert partial.read_bytes() == b"valid-partial-checkpoint"
    assert not _process_is_running(int(child_pid.read_text()))


def test_successful_parent_cannot_leave_a_running_child(tmp_path):
    child_pid = tmp_path / "child.pid"
    code = (
        "import subprocess, sys; from pathlib import Path; "
        "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)']); "
        f"Path({str(child_pid)!r}).write_text(str(child.pid))"
    )
    result = _run(code, timeout_seconds=5, terminate_grace_seconds=0.1, on_event=lambda event: None)
    assert result.status == "completed"
    assert not _process_is_running(int(child_pid.read_text()))


def test_events_and_timeout_do_not_disclose_arguments_or_environment():
    secret = "do-not-log-this-secret"
    events = []
    with pytest.raises(ExecutionTimeoutError) as caught:
        run_bounded(
            [sys.executable, "-c", "import time; time.sleep(60)", secret],
            stage="render", timeout_seconds=0.2, terminate_grace_seconds=0.1,
            env={**os.environ, "TEST_WATCHDOG_SECRET": secret}, on_event=events.append,
        )
    assert secret not in json.dumps(events)
    assert secret not in str(caught.value)
    assert secret not in repr(caught.value.result)


def test_launch_failure_is_explicit_without_logging_command(tmp_path):
    events = []
    with pytest.raises(ExecutionWatchdogError):
        run_bounded([str(tmp_path / "missing-secret-executable")], stage="render",
                    timeout_seconds=1, on_event=events.append)
    assert events[-1]["status"] == "launch_failed"
    assert "missing-secret" not in json.dumps(events)


def test_cli_timeout_has_exit_124_and_finite_heartbeats(tmp_path):
    script = Path(__file__).parent / "scripts" / "run_bounded.py"
    result = subprocess.run(
        [sys.executable, str(script), "--stage", "render", "--timeout", "0.25",
         "--heartbeat", "0.1", "--grace", "0.1", "--log", str(tmp_path / "render.log"),
         "--", sys.executable, "-c", "import time; time.sleep(60)"],
        capture_output=True, text=True, timeout=5,
    )
    assert result.returncode == 124
    events = [json.loads(line) for line in result.stderr.splitlines()]
    assert events[0]["status"] == "started"
    assert events[-1]["status"] == "timed_out"


@pytest.mark.skipif(os.name == "nt", reason="POSIX nested process-group regression")
def test_outer_deadline_stops_nested_watchdog_separate_process_group(tmp_path):
    child_pid = tmp_path / "nested-child.pid"
    child_code = (
        "import os,time; from pathlib import Path; "
        f"Path({str(child_pid)!r}).write_text(str(os.getpid())); time.sleep(60)"
    )
    nested_code = (
        "import sys; from backend.services.runtime.execution_watchdog import run_bounded; "
        f"run_bounded([sys.executable, '-c', {child_code!r}], "
        "stage='nested', timeout_seconds=30, terminate_grace_seconds=3)"
    )
    before_handler = signal.getsignal(signal.SIGTERM)
    with pytest.raises(ExecutionTimeoutError):
        _run(nested_code, timeout_seconds=0.8, terminate_grace_seconds=0.4,
             cwd=Path(__file__).parent, log_path=tmp_path / "nested.log",
             on_event=lambda event: None)
    assert child_pid.exists()
    assert not _process_is_running(int(child_pid.read_text()))
    assert signal.getsignal(signal.SIGTERM) is before_handler


@pytest.mark.skipif(os.name == "nt", reason="SIGTERM CLI interruption test is POSIX-specific")
def test_cli_sigterm_stops_the_stage(tmp_path):
    pid_file = tmp_path / "stage.pid"
    script = Path(__file__).parent / "scripts" / "run_bounded.py"
    code = f"import os,time; from pathlib import Path; Path({str(pid_file)!r}).write_text(str(os.getpid())); time.sleep(60)"
    process = subprocess.Popen(
        [sys.executable, str(script), "--stage", "interrupt", "--timeout", "30", "--grace", "0.1",
         "--", sys.executable, "-c", code], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        deadline = time.monotonic() + 3
        while not pid_file.exists() and time.monotonic() < deadline:
            time.sleep(0.02)
        assert pid_file.exists()
        process.send_signal(signal.SIGTERM)
        assert process.wait(timeout=3) == 130
        assert not _process_is_running(int(pid_file.read_text()))
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=2)
