"""Bound a production stage and its subprocess tree without deleting its work.

Run a whole benchmark with this wrapper to include in-process Whisper/OpenCLIP
work in the deadline. POSIX children inherit a dedicated process group. Windows
children inherit a kill-on-close Job Object; the root is launched suspended so
it cannot start an untracked child before assignment. Commands and environment
values are deliberately absent from events and errors.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time
from typing import Callable, Mapping, Sequence


@dataclass(frozen=True)
class ExecutionResult:
    stage: str
    status: str
    returncode: int | None
    elapsed_seconds: float
    timeout_seconds: float
    pid: int | None


class ExecutionWatchdogError(RuntimeError):
    """A stage could not be launched with a safe process boundary."""


class ExecutionTimeoutError(TimeoutError):
    def __init__(self, result: ExecutionResult):
        self.result = result
        super().__init__(
            f"Stage {result.stage!r} exceeded its {result.timeout_seconds:g}s deadline; "
            "its process tree was stopped and existing files were preserved."
        )


def _finite_seconds(value: float, name: str, *, allow_zero: bool = False) -> float:
    value = float(value)
    if not math.isfinite(value) or value < 0 or (value == 0 and not allow_zero):
        raise ValueError(f"{name} must be finite and {'nonnegative' if allow_zero else 'positive'}")
    return value


def _default_event(event: dict) -> None:
    print(json.dumps(event, sort_keys=True), file=sys.stderr, flush=True)


class _WindowsJob:
    """Use documented Win32 APIs; fail closed when job assignment is forbidden."""

    def __init__(self) -> None:
        import ctypes
        from ctypes import wintypes

        self.ctypes = ctypes
        self.wintypes = wintypes
        self.api = ctypes.WinDLL("kernel32", use_last_error=True)
        size_t = ctypes.c_size_t

        class BasicLimits(ctypes.Structure):
            _fields_ = [
                ("PerProcessUserTimeLimit", ctypes.c_longlong),
                ("PerJobUserTimeLimit", ctypes.c_longlong),
                ("LimitFlags", wintypes.DWORD),
                ("MinimumWorkingSetSize", size_t),
                ("MaximumWorkingSetSize", size_t),
                ("ActiveProcessLimit", wintypes.DWORD),
                ("Affinity", size_t),
                ("PriorityClass", wintypes.DWORD),
                ("SchedulingClass", wintypes.DWORD),
            ]

        class IoCounters(ctypes.Structure):
            _fields_ = [(name, ctypes.c_ulonglong) for name in (
                "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
                "ReadTransferCount", "WriteTransferCount", "OtherTransferCount",
            )]

        class ExtendedLimits(ctypes.Structure):
            _fields_ = [
                ("BasicLimitInformation", BasicLimits),
                ("IoInfo", IoCounters),
                ("ProcessMemoryLimit", size_t), ("JobMemoryLimit", size_t),
                ("PeakProcessMemoryUsed", size_t), ("PeakJobMemoryUsed", size_t),
            ]

        class ThreadEntry(ctypes.Structure):
            _fields_ = [
                ("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD),
                ("th32ThreadID", wintypes.DWORD), ("th32OwnerProcessID", wintypes.DWORD),
                ("tpBasePri", wintypes.LONG), ("tpDeltaPri", wintypes.LONG),
                ("dwFlags", wintypes.DWORD),
            ]

        self.ThreadEntry = ThreadEntry
        signatures = {
            "CreateJobObjectW": ([ctypes.c_void_p, wintypes.LPCWSTR], wintypes.HANDLE),
            "SetInformationJobObject": ([wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD], wintypes.BOOL),
            "AssignProcessToJobObject": ([wintypes.HANDLE, wintypes.HANDLE], wintypes.BOOL),
            "OpenProcess": ([wintypes.DWORD, wintypes.BOOL, wintypes.DWORD], wintypes.HANDLE),
            "CloseHandle": ([wintypes.HANDLE], wintypes.BOOL),
            "CreateToolhelp32Snapshot": ([wintypes.DWORD, wintypes.DWORD], wintypes.HANDLE),
            "Thread32First": ([wintypes.HANDLE, ctypes.POINTER(ThreadEntry)], wintypes.BOOL),
            "Thread32Next": ([wintypes.HANDLE, ctypes.POINTER(ThreadEntry)], wintypes.BOOL),
            "OpenThread": ([wintypes.DWORD, wintypes.BOOL, wintypes.DWORD], wintypes.HANDLE),
            "ResumeThread": ([wintypes.HANDLE], wintypes.DWORD),
        }
        for name, (args, result) in signatures.items():
            function = getattr(self.api, name)
            function.argtypes = args
            function.restype = result
        self.handle = self.api.CreateJobObjectW(None, None)
        if not self.handle:
            raise ExecutionWatchdogError("Cannot create Windows execution Job Object")
        limits = ExtendedLimits()
        limits.BasicLimitInformation.LimitFlags = 0x00002000  # KILL_ON_JOB_CLOSE
        if not self.api.SetInformationJobObject(
            self.handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)
        ):
            self.close()
            raise ExecutionWatchdogError("Cannot set Windows job process-tree protection")

    def assign_and_resume(self, pid: int) -> None:
        # PROCESS_TERMINATE | PROCESS_SET_QUOTA | PROCESS_QUERY_INFORMATION
        process_handle = self.api.OpenProcess(0x0001 | 0x0100 | 0x0400, False, pid)
        if not process_handle:
            raise ExecutionWatchdogError("Cannot open suspended stage for Windows job assignment")
        try:
            if not self.api.AssignProcessToJobObject(self.handle, process_handle):
                raise ExecutionWatchdogError(
                    "Windows job assignment denied; stage was not allowed to run unbounded"
                )
        finally:
            self.api.CloseHandle(process_handle)

        snapshot = self.api.CreateToolhelp32Snapshot(0x00000004, 0)  # SNAPTHREAD
        if snapshot == self.ctypes.c_void_p(-1).value:
            raise ExecutionWatchdogError("Cannot inspect suspended Windows stage threads")
        resumed = False
        try:
            entry = self.ThreadEntry()
            entry.dwSize = self.ctypes.sizeof(entry)
            valid = self.api.Thread32First(snapshot, self.ctypes.byref(entry))
            while valid:
                if entry.th32OwnerProcessID == pid:
                    thread = self.api.OpenThread(0x0002, False, entry.th32ThreadID)
                    if thread:
                        try:
                            if self.api.ResumeThread(thread) != 0xFFFFFFFF:
                                resumed = True
                        finally:
                            self.api.CloseHandle(thread)
                valid = self.api.Thread32Next(snapshot, self.ctypes.byref(entry))
        finally:
            self.api.CloseHandle(snapshot)
        if not resumed:
            raise ExecutionWatchdogError("Cannot resume protected Windows stage")

    def close(self) -> None:
        if self.handle:
            self.api.CloseHandle(self.handle)
            self.handle = None


def _group_exists(pid: int) -> bool:
    try:
        os.killpg(pid, 0)
        return True
    except ProcessLookupError:
        return False


def _stop_tree(process: subprocess.Popen, job: _WindowsJob | None, grace: float) -> None:
    """Cleanup is itself bounded; never wait indefinitely for a child to exit."""
    if os.name == "nt":
        if process.poll() is None:
            try:
                process.send_signal(signal.CTRL_BREAK_EVENT)
                process.wait(timeout=grace)
            except (OSError, subprocess.TimeoutExpired):
                pass
        if job is not None:
            job.close()  # Also kills descendants after a successful root exit.
    else:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        deadline = time.monotonic() + grace
        while _group_exists(process.pid) and time.monotonic() < deadline:
            process.poll()
            time.sleep(min(0.05, max(0, deadline - time.monotonic())))
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    try:
        process.wait(timeout=1.0)
    except subprocess.TimeoutExpired:
        # An OS-level uninterruptible process cannot be made to reap here, but
        # it must never turn the watchdog into another indefinite waiter.
        raise ExecutionWatchdogError("OS did not reap terminated stage within cleanup deadline") from None


def run_bounded(
    command: Sequence[str],
    *,
    stage: str,
    timeout_seconds: float,
    heartbeat_seconds: float = 15.0,
    terminate_grace_seconds: float = 3.0,
    cwd: str | Path | None = None,
    env: Mapping[str, str] | None = None,
    log_path: str | Path | None = None,
    on_event: Callable[[dict], None] | None = None,
    stdin_data: bytes | None = None,
) -> ExecutionResult:
    """Run without a shell, returning failure exit codes and raising on timeout.

    A deadline is never extended by log output or heartbeat activity. Child
    stdout/stderr are inherited, or appended directly to ``log_path`` (no pipes
    to fill and deadlock). Existing output/cache files are never removed. The
    event callback receives only stage, PID, timing, status and return code.
    POSIX workloads must not intentionally daemonize out of their session.
    """
    timeout = _finite_seconds(timeout_seconds, "timeout_seconds")
    heartbeat = _finite_seconds(heartbeat_seconds, "heartbeat_seconds")
    grace = _finite_seconds(terminate_grace_seconds, "terminate_grace_seconds", allow_zero=True)
    if not isinstance(stage, str) or not stage.strip() or len(stage) > 128 or any(ord(c) < 32 for c in stage):
        raise ValueError("stage must be a nonempty, single-line label of at most 128 characters")
    if isinstance(command, (str, bytes)) or not command or any(not isinstance(arg, str) or "\0" in arg for arg in command):
        raise ValueError("command must be a nonempty sequence of string arguments")
    if stdin_data is not None and not isinstance(stdin_data, bytes):
        raise ValueError("stdin_data must be bytes")
    emit = on_event or _default_event
    started = time.monotonic()
    process = None
    job = None
    log_handle = None
    previous_sigterm = None
    handling_sigterm = threading.current_thread() is threading.main_thread()

    def terminate_stage(_signum, _frame):
        # A containing watchdog can terminate this Python process while our
        # child owns a separate process group. Turn that signal into cleanup,
        # rather than allowing the nested group's FFmpeg to become orphaned.
        raise KeyboardInterrupt

    if handling_sigterm:
        previous_sigterm = signal.signal(signal.SIGTERM, terminate_stage)

    def result(status: str) -> ExecutionResult:
        return ExecutionResult(stage, status, process.poll() if process else None,
                               round(time.monotonic() - started, 3), timeout,
                               process.pid if process else None)

    try:
        if log_path is not None:
            path = Path(log_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            log_handle = path.open("ab", buffering=0)
        options = dict(cwd=cwd, env=env, stdout=log_handle,
                       stderr=subprocess.STDOUT if log_handle else None,
                       stdin=subprocess.PIPE if stdin_data is not None else subprocess.DEVNULL)
        if os.name == "nt":
            job = _WindowsJob()
            # CREATE_SUSPENDED | CREATE_NEW_PROCESS_GROUP: assign before any code runs.
            options["creationflags"] = 0x00000004 | 0x00000200
        else:
            options["start_new_session"] = True
        try:
            process = subprocess.Popen(list(command), **options)
        except OSError:
            emit(asdict(result("launch_failed")))
            raise ExecutionWatchdogError(f"Stage {stage!r} could not start") from None
        if job is not None:
            job.assign_and_resume(process.pid)
        if stdin_data is not None:
            def send_input():
                try:
                    process.stdin.write(stdin_data)
                    process.stdin.close()
                except (BrokenPipeError, OSError):
                    pass
            threading.Thread(target=send_input, daemon=True,
                             name=f"stdin-{stage}").start()
        emit(asdict(result("started")))
        next_heartbeat = time.monotonic() + heartbeat
        deadline = started + timeout
        while process.poll() is None:
            now = time.monotonic()
            if now >= deadline:
                _stop_tree(process, job, grace)
                timed_out = result("timed_out")
                emit(asdict(timed_out))
                raise ExecutionTimeoutError(timed_out)
            if now >= next_heartbeat:
                emit(asdict(result("running")))
                next_heartbeat = now + heartbeat
            time.sleep(min(0.1, max(0, deadline - now), max(0, next_heartbeat - now)))
        finished = result("completed" if process.returncode == 0 else "failed")
        _stop_tree(process, job, grace)
        emit(asdict(finished))
        return finished
    except (KeyboardInterrupt, SystemExit):
        if process is not None:
            # An outer watchdog may be counting down its own kill deadline.
            # Stop this nested tree immediately, before that parent kills us.
            _stop_tree(process, job, 0)
        emit(asdict(result("interrupted")))
        raise
    finally:
        # Covers callback failures and Windows assignment failures too.
        if process is not None and process.poll() is None:
            if job is not None:
                job.close()
                process.kill()  # Assignment may have failed before it joined the job.
            _stop_tree(process, job, grace)
        if job is not None:
            job.close()
        if log_handle is not None:
            log_handle.close()
        if handling_sigterm:
            signal.signal(signal.SIGTERM, previous_sigterm)
