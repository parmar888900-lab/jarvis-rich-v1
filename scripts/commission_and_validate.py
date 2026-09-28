#!/usr/bin/env python3
"""One bounded, private Windows commissioning run with a safe evidence bundle.

Run with the installed venv Python. No upload, OAuth, account creation, DB
editing, or perceptual approval is performed. Existing zero allocations stay
sealed. On restart, the commissioning script returns the existing job.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.services.runtime.execution_watchdog import (  # noqa: E402
    ExecutionTimeoutError, ExecutionWatchdogError, run_bounded,
)

JOB_PATTERN = re.compile(r"private_qa_job=([0-9a-fA-F-]{36}) state=([A-Z_]+)")
DIAGNOSTIC_KEYS = frozenset({
    "topic", "production_score", "quality", "research_confidence",
    "evidence", "visual_supply", "visual", "weakest", "source_count",
    "originality", "threshold", "reason",
})
FINAL_STATES = frozenset({"QA", "APPROVED", "COMPLETE", "FAILED", "HUMAN_ACTION_REQUIRED"})


def _json_object(text: str) -> dict:
    """Decode the first standalone JSON object from a bounded child log."""
    decoder = json.JSONDecoder()
    for offset, character in enumerate(text):
        if character != "{":
            continue
        try:
            value, _ = decoder.raw_decode(text[offset:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    raise ValueError("No JSON state found in checker output")


def _diagnostics(text: str) -> list[dict]:
    out = []
    for line in text.splitlines():
        if not line.startswith("{"):
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and "topic" in data and "reason" in data:
            out.append({key: data[key] for key in DIAGNOSTIC_KEYS if key in data})
    return out[:4]


async def _job_state(job_id: str) -> dict | None:
    # Use the configured database/ORM; never guess a path or mutate SQLite.
    from backend.database import async_session
    from backend.models.network_job import NetworkJob

    async with async_session() as session:
        job = await session.get(NetworkJob, job_id)
        if job is None:
            return None
        return {
            "id": job.id, "state": job.state, "attempt": job.attempt,
            "failure_reason": job.failure_reason,
            "retry_after": job.retry_after.isoformat() if job.retry_after else None,
            "render_path": (job.artifacts or {}).get("render"),
            "lineage": {key: (job.lineage or {}).get(key) for key in (
                "production_cycle", "render_sha256", "script_sha256",
                "evidence_ids", "package_dir") if key in (job.lineage or {})},
        }


def _stage(command: list[str], *, name: str, deadline: int, log: Path) -> int:
    try:
        outcome = run_bounded(
            command, stage=name, timeout_seconds=deadline,
            heartbeat_seconds=20, terminate_grace_seconds=5,
            log_path=log, cwd=ROOT, env=os.environ.copy(),
        )
        return outcome.returncode or 0
    except ExecutionTimeoutError:
        return 124
    except (ExecutionWatchdogError, OSError, ValueError):
        return 125


def _probe_video(path: Path, log_dir: Path) -> dict:
    if not path.is_file() or path.stat().st_size == 0:
        return {"valid": False, "reason": "render_missing_or_empty"}
    binary = shutil.which("ffprobe")
    if not binary:
        return {"valid": False, "reason": "ffprobe_unavailable"}
    log = log_dir / "ffprobe.log"
    code = _stage([
        binary, "-v", "error", "-show_entries",
        "format=duration,size:stream=codec_name,codec_type,width,height,r_frame_rate",
        "-of", "json", str(path),
    ], name="private-render-probe", deadline=30, log=log)
    if code:
        return {"valid": False, "reason": "ffprobe_failed", "exit_code": code}
    try:
        probe = _json_object(log.read_text(encoding="utf-8"))
        streams = probe.get("streams", [])
        video = next(s for s in streams if s.get("codec_type") == "video")
        audio = next(s for s in streams if s.get("codec_type") == "audio")
        duration = float(probe["format"]["duration"])
        valid = 0 < duration <= 180 and (video.get("width"), video.get("height"),
                                          video.get("r_frame_rate")) in {
                                              (1080, 1920, "30/1"), (1080, 1920, "30")}
        digest = hashlib.sha256()
        with path.open("rb") as source:
            for block in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(block)
        return {
            "valid": valid, "duration_seconds": duration,
            "width": video.get("width"), "height": video.get("height"),
            "frame_rate": video.get("r_frame_rate"),
            "video_codec": video.get("codec_name"), "audio_codec": audio.get("codec_name"),
            "size_bytes": path.stat().st_size, "sha256": digest.hexdigest(),
        }
    except (OSError, ValueError, KeyError, StopIteration, TypeError):
        return {"valid": False, "reason": "malformed_probe_output"}


def _write(report: dict, directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    temporary = directory / "evidence.json.tmp"
    temporary.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    temporary.replace(directory / "evidence.json")
    summary = [
        f"Boundary: {report['boundary']}",
        f"Job: {report.get('job', {}).get('id', 'none') if report.get('job') else 'none'}",
        f"State: {report.get('job', {}).get('state', 'none') if report.get('job') else 'none'}",
        f"Render: {report.get('render_path') or 'none'}",
        f"Technical video valid: {report.get('video', {}).get('valid', False)}",
        "Perceptual Rich V1 status: NOT APPROVED by this command",
        "Public publishing: OFF (forced for child processes)",
        ("Network publishing: OFF (checker verified)"
         if report.get("network_publishing_enabled") is False
         else "Network publishing: UNVERIFIED; commissioning stopped"),
    ]
    (directory / "summary.txt").write_text("\n".join(summary) + "\n", encoding="utf-8")
    print("\n".join(summary), flush=True)
    print(f"Evidence: {directory / 'evidence.json'}", flush=True)


def execute(channel_id: str, *, wait_seconds: int, report_dir: Path) -> dict:
    if not 0 <= wait_seconds <= 8000:
        raise ValueError("wait_seconds must be bounded to 0–8000")
    os.environ["JARVIS_PUBLIC_PUBLISH_ENABLED"] = "false"
    # Child output is retained locally for diagnosis, but excluded from the
    # shareable evidence directory because providers may print sensitive text.
    log_dir = ROOT / "generated" / "logs" / "private-commission" / report_dir.name
    log_dir.mkdir(parents=True, exist_ok=True)
    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "branch": None, "git_head": None, "channel_id": channel_id,
        "public_publishing_enabled": False, "network_publishing_enabled": None,
        "boundary": "preflight", "human_action_required": [],
        "internal_log_dir": str(log_dir),
    }
    for name, args in (("branch", ["branch", "--show-current"]), ("git_head", ["rev-parse", "HEAD"])):
        try:
            report[name] = subprocess.run(
                ["git", *args], cwd=ROOT, capture_output=True, text=True,
                timeout=10, check=True,
            ).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            report["boundary"] = "git_identity_unavailable"
            return report
    if report["branch"] != "sprint/rich-v1-20260920":
        report["boundary"] = "wrong_branch"
        return report
    checker = log_dir / "checker.log"
    code = _stage([sys.executable, str(ROOT / "scripts" / "check_jarvis.py")],
                  name="network-preflight", deadline=90, log=checker)
    if code:
        report.update(boundary="checker_failed", checker_exit_code=code)
        return report
    try:
        state = _json_object(checker.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        report["boundary"] = "checker_output_invalid"
        return report
    report["checker"] = state
    report["network_publishing_enabled"] = state.get("network_publishing_enabled")
    if state.get("public_publishing_enabled") is not False or state.get("network_publishing_enabled") is not False:
        report["boundary"] = "publishing_invariant_failed"
        return report
    if state.get("production_enabled") is not True:
        report["boundary"] = "production_paused"
        return report
    missing = [item for item in state.get("missing_production_dependencies", []) if item != "youtube_token"]
    if missing:
        report.update(boundary="runtime_unready", missing_dependencies=missing)
        return report
    commission = log_dir / "commission.log"
    code = _stage([sys.executable, str(ROOT / "scripts" / "commission_network_job.py"), channel_id],
                  name="network-commission", deadline=360, log=commission)
    try:
        output = commission.read_text(encoding="utf-8", errors="replace")
    except OSError:
        output = ""
    report["candidates"] = _diagnostics(output)
    if code:
        report.update(boundary="commission_failed", commission_exit_code=code)
        return report
    matches = JOB_PATTERN.findall(output)
    if not matches:
        report["boundary"] = "no_production_ready_candidate"
        return report
    job_id = matches[-1][0]
    report["job"] = asyncio.run(_job_state(job_id))
    if report["job"] is None:
        report["boundary"] = "commissioned_job_missing"
        return report
    report["boundary"] = "job_persisted"
    if report["job"]["state"] not in FINAL_STATES and wait_seconds:
        deadline = time.monotonic() + wait_seconds
        # The normal scheduled supervisor may already own the job. Never
        # start a second long-running supervisor; a one-shot worker's OS lock
        # rejects duplicates. Its entire tree remains bounded.
        heartbeat = state.get("supervisor") or {}
        if heartbeat.get("fresh") is not True:
            code = _stage([sys.executable, str(ROOT / "scripts" / "run_network_supervisor.py"),
                           "--once"], name="network-one-shot",
                          deadline=min(7300, max(1, wait_seconds)),
                          log=log_dir / "supervisor.log")
            report["one_shot_exit_code"] = code
        while time.monotonic() < deadline:
            report["job"] = asyncio.run(_job_state(job_id))
            if report["job"] and report["job"]["state"] in FINAL_STATES:
                break
            time.sleep(min(15, max(0, deadline - time.monotonic())))
    report["job"] = asyncio.run(_job_state(job_id))
    if report["job"]:
        report["boundary"] = f"job_{report['job']['state'].lower()}"
        render = report["job"].get("render_path")
        if render:
            render_path = Path(render)
            if not render_path.is_absolute():
                render_path = ROOT / render_path
            report["render_path"] = str(render_path)
            report["video"] = _probe_video(render_path, log_dir)
            recorded_hash = report["job"].get("lineage", {}).get("render_sha256")
            if (recorded_hash and report["video"].get("sha256")
                    and recorded_hash != report["video"]["sha256"]):
                report["video"]["valid"] = False
                report["video"]["reason"] = "render_changed_since_qa"
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("channel_id", help="Existing private ACTIVE channel UUID")
    parser.add_argument("--wait-seconds", type=int, default=7500)
    parser.add_argument("--report-dir", type=Path)
    args = parser.parse_args(argv)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    directory = args.report_dir or ROOT / "generated" / "reports" / f"private-commission-{stamp}"
    directory.mkdir(parents=True, exist_ok=True)
    try:
        report = execute(args.channel_id, wait_seconds=args.wait_seconds, report_dir=directory)
    except Exception as exc:
        # Never serialize exception text: providers may include credentials.
        report = {"timestamp": datetime.now(timezone.utc).isoformat(),
                  "boundary": "wrapper_error", "error_type": type(exc).__name__,
                  "public_publishing_enabled": False,
                  "network_publishing_enabled": None}
    _write(report, directory)
    return 0 if (report["boundary"] == "no_production_ready_candidate" or
                 (report["boundary"] == "job_qa" and report.get("video", {}).get("valid"))) else 1


if __name__ == "__main__":
    raise SystemExit(main())
