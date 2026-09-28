"""Pure boundary tests for the Windows evidence command; no account actions."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from scripts import commission_and_validate as command


def test_preflight_fails_closed_without_starting_commission():
    with tempfile.TemporaryDirectory() as folder:
        directory = Path(folder)

        def stage(_argv, *, name, deadline, log):
            assert name == "network-preflight"
            log.write_text(json.dumps({
                "public_publishing_enabled": False,
                "network_publishing_enabled": True,
                "production_enabled": True,
                "missing_production_dependencies": [],
            }), encoding="utf-8")
            return 0

        with patch.object(command, "_stage", side_effect=stage) as calls:
            result = command.execute("channel-id", wait_seconds=0, report_dir=directory)
        assert result["boundary"] == "publishing_invariant_failed"
        assert calls.call_count == 1
        assert not list(directory.glob("*.log"))


def test_persisted_qa_report_probes_existing_artifact_without_upload():
    with tempfile.TemporaryDirectory() as folder:
        directory = Path(folder)
        render = directory / "completed.mp4"
        render.write_bytes(b"previously completed video")
        job_id = "12345678-1234-1234-1234-123456789abc"
        state = {
            "id": job_id, "state": "QA", "attempt": 0,
            "failure_reason": None, "render_path": str(render),
            "lineage": {"render_sha256": "recorded-hash"},
        }

        def stage(_argv, *, name, deadline, log):
            if name == "network-preflight":
                log.write_text(json.dumps({
                    "public_publishing_enabled": False,
                    "network_publishing_enabled": False,
                    "production_enabled": True,
                    "missing_production_dependencies": ["youtube_token"],
                    "supervisor": {"fresh": False},
                }), encoding="utf-8")
            elif name == "network-commission":
                log.write_text(
                    '{"topic":"Webb mirror","quality":0.72,"evidence":0.63,'
                    '"visual":0.72,"weakest":0.63,"reason":"eligible_for_originality_reservation"}\n'
                    f"private_qa_job={job_id} state=QUEUED\n", encoding="utf-8")
            else:
                assert name == "private-render-probe"
                log.write_text(json.dumps({
                    "format": {"duration": "33.3"},
                    "streams": [
                        {"codec_type": "video", "codec_name": "h264",
                         "width": 1080, "height": 1920, "r_frame_rate": "30/1"},
                        {"codec_type": "audio", "codec_name": "aac"},
                    ],
                }), encoding="utf-8")
            return 0

        async def job_state(_id):
            assert _id == job_id
            return state

        with patch.object(command, "_stage", side_effect=stage), \
             patch.object(command, "_job_state", side_effect=job_state), \
             patch.object(command.shutil, "which", return_value="/usr/bin/ffprobe"):
            result = command.execute("channel-id", wait_seconds=0, report_dir=directory)
        assert result["boundary"] == "job_qa"
        assert result["video"]["valid"] is True
        assert result["video"]["width"] == 1080
        assert result["candidates"][0]["evidence"] == 0.63
        assert "token" not in json.dumps(result.get("candidates"))
        assert not list(directory.glob("*.log"))


def test_probe_rejects_wrong_geometry_and_preserves_file():
    with tempfile.TemporaryDirectory() as folder:
        directory = Path(folder)
        render = directory / "render.mp4"
        render.write_bytes(b"content")

        def stage(_argv, *, name, deadline, log):
            log.write_text(json.dumps({
                "format": {"duration": "33.3"},
                "streams": [{"codec_type": "video", "width": 720,
                             "height": 1280, "r_frame_rate": "30/1"},
                            {"codec_type": "audio"}],
            }), encoding="utf-8")
            return 0

        with patch.object(command, "_stage", side_effect=stage), \
             patch.object(command.shutil, "which", return_value="/usr/bin/ffprobe"):
            outcome = command._probe_video(render, directory)
        assert outcome["valid"] is False
        assert render.read_bytes() == b"content"
