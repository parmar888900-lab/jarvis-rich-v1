"""Resume only sound finishing from a verified narration-only final MP4.

Video packets are copied and verified unchanged. This does not re-run or claim
to pass visual/semantic QA; those findings belong to the hashed parent render.
Every expensive step, including procedural synthesis, runs under the watchdog.
"""

from __future__ import annotations

import argparse
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.services.runtime.execution_watchdog import run_bounded
from backend.services.runtime.runtime_config import RuntimeConfig
from backend.services.video.sound_design import OriginalSoundDesigner


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def checked_stage(command: list[str], stage: str, seconds: float, log: Path) -> None:
    result = run_bounded(command, stage=stage, timeout_seconds=seconds,
                         heartbeat_seconds=10, log_path=log)
    if result.returncode != 0:
        raise RuntimeError(f"{stage} failed with exit {result.returncode}; see {log}")


def probe(path: Path, log: Path) -> dict:
    checked_stage(["ffprobe", "-v", "error", "-show_format", "-show_streams",
                   "-of", "json", str(path)], "audio-finish-probe", 15, log)
    return json.loads(log.read_text(encoding="utf-8"))


def video_hash(path: Path, log: Path) -> str:
    checked_stage(["ffmpeg", "-v", "error", "-nostdin", "-i", str(path),
                   "-map", "0:v:0", "-c", "copy", "-f", "hash", "-hash",
                   "sha256", "-"], "video-packet-verification", 30, log)
    return log.read_text(encoding="utf-8").strip()


def refinish(*, source: Path, expected_sha256: str, output: Path,
             cue_times: list[float], narration_only_confirmed: bool) -> dict:
    if not narration_only_confirmed:
        raise ValueError("Parent must be verified narration-only to avoid stacking sound beds")
    if source.resolve() == output.resolve() or output.exists():
        raise ValueError("Use a new output path; completed renders are never overwritten")
    if file_hash(source) != expected_sha256.lower():
        raise ValueError("Parent checksum differs from the verified render")
    output.parent.mkdir(parents=True, exist_ok=True)
    # A fresh attempt directory keeps failed-stage evidence without log collisions.
    import tempfile
    attempt = Path(tempfile.mkdtemp(prefix=output.stem + "_", dir=output.parent))
    original = probe(source, attempt / "parent_probe.json")
    duration = float(original["format"]["duration"])
    audio_streams = [s for s in original["streams"] if s["codec_type"] == "audio"]
    video_streams = [s for s in original["streams"] if s["codec_type"] == "video"]
    if len(video_streams) != 1 or len(audio_streams) != 1:
        raise ValueError("Expected exactly one picture and one narration stream")
    narration = attempt / "narration.wav"
    checked_stage(["ffmpeg", "-v", "error", "-nostdin", "-n", "-i", str(source),
                   "-map", "0:a:0", "-c:a", "pcm_s16le", str(narration)],
                  "recover-narration", 30, attempt / "extract.log")
    request = attempt / "sound_request.json"
    request.write_text(json.dumps({"narration": str(narration.resolve()),
                                  "duration": duration, "cues": cue_times,
                                  "generated_dir": str(attempt.resolve())}), encoding="utf-8")
    sound_manifest = attempt / "sound_design.json"
    checked_stage([sys.executable, str(Path(__file__).resolve()), "--synthesis-request",
                   str(request), "--synthesis-result", str(sound_manifest)],
                  "original-sound-synthesis", 120, attempt / "synthesis.log")
    sound = json.loads(sound_manifest.read_text(encoding="utf-8"))
    partial = attempt / "candidate.mp4"
    # normalize=0 mirrors the renderer's additive CompositeAudioClip mix.
    checked_stage(["ffmpeg", "-v", "error", "-nostdin", "-n", "-i", str(source),
                   "-i", sound["audio_path"], "-filter_complex",
                   "[0:a:0][1:a:0]amix=inputs=2:duration=first:normalize=0[mix]",
                   "-map", "0:v:0", "-map", "[mix]", "-c:v", "copy", "-c:a",
                   "aac", "-b:a", "192k", "-movflags", "+faststart", str(partial)],
                  "sound-finish-mux", 90, attempt / "mux.log")
    finished = probe(partial, attempt / "finished_probe.json")
    before = video_hash(source, attempt / "parent_video.sha256")
    after = video_hash(partial, attempt / "finished_video.sha256")
    if before != after:
        raise RuntimeError("Video packets changed; candidate preserved but not promoted")
    if abs(float(finished["format"]["duration"]) - duration) > 0.05:
        raise RuntimeError("Finish duration changed; candidate preserved but not promoted")
    partial.rename(output)
    result = {
        "status": "complete", "public_release": False,
        "quality_gate": "PENDING_REAL_RENDER_INSPECTION",
        "source": str(source.resolve()), "source_sha256": expected_sha256.lower(),
        "output": str(output.resolve()), "output_sha256": file_hash(output),
        "size_bytes": output.stat().st_size,
        "duration": float(finished["format"]["duration"]), "parent_duration": duration,
        "video_packets_unchanged": True, "video_stream_sha256": after,
        "semantic_matches_recomputed": False,
        "inherited_visual_qa": "Unchanged picture from checksum-verified parent",
        "sound_design": sound, "attempt_directory": str(attempt.resolve()),
    }
    output.with_suffix(".json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--sha256")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--cue-times", default="0")
    parser.add_argument("--narration-only", action="store_true")
    parser.add_argument("--synthesis-request", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--synthesis-result", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.synthesis_request:
        data = json.loads(args.synthesis_request.read_text(encoding="utf-8"))
        config = replace(RuntimeConfig.from_environment(), generated_dir=Path(data["generated_dir"]))
        manifest = OriginalSoundDesigner(config).generate(
            narration_path=data["narration"], duration=data["duration"], cue_times=data["cues"])
        args.synthesis_result.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        return
    if not all((args.source, args.sha256, args.output)):
        parser.error("--source, --sha256 and --output are required")
    print(json.dumps(refinish(source=args.source, expected_sha256=args.sha256,
                             output=args.output, cue_times=[float(x) for x in args.cue_times.split(",")],
                             narration_only_confirmed=args.narration_only), indent=2))


if __name__ == "__main__":
    main()
