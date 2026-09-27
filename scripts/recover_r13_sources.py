"""Recover the three hashed official R13 sources and match source timestamps.

This forensic recovery never calls the LLM or semantic matcher and never claims
new semantic approvals. Parent picture matching is evidence of lineage only.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.services.runtime.execution_watchdog import run_bounded
from backend.services.video.media_sources.nasa import NasaVideoProvider

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "generated/benchmarks/r15_recovery"
IDS = ["Webb_Mirror_Phasing_ChamberA_Social_media-h264",
       "Mission_Overview_MASTER-h264", "GSFC_201908006_JWST_m13273_SMS_Deploy"]
STARTS = [0, 1.833333, 3.933333, 6.333333, 9.233333, 12.166667,
          15.1, 18, 20.933333, 23.866667, 26.766667, 30.066667]


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def bounded(cmd: list[str], stage: str, seconds: float = 90) -> Path:
    log = OUT / (stage + ".log")
    r = run_bounded(cmd, stage=stage, timeout_seconds=seconds,
                    heartbeat_seconds=10, log_path=log)
    if r.returncode:
        raise RuntimeError(f"{stage} failed: {r.returncode}; {log}")
    return log


def download_one(index: int) -> None:
    nasa_id = IDS[index]
    p = NasaVideoProvider(download_root=str(OUT / "sources"))
    url = p._best_video_url(nasa_id)
    if not url:
        raise RuntimeError(f"No official asset found: {nasa_id}")
    # NASA API advertises http URLs; same NASA assets endpoint supports TLS.
    url = url.replace("http://", "https://", 1)
    path = p._download(url=url, content_id="r13-source-recovery", nasa_id=nasa_id)
    if path is None:
        raise RuntimeError(f"Download failed: {nasa_id}")
    record = {"provider": "NASA Images", "nasa_id": nasa_id,
              "source_url": url, "source_api": p.ASSET_URL.format(nasa_id=nasa_id),
              "license_name": "NASA Media", "license_url": "https://www.nasa.gov/nasa-brand-center/images-and-media/",
              "usage_basis": "Inherited R13 official NASA source approval; NASA source audio not used",
              "creator": "NASA", "public_release": False,
              "acquired_at": datetime.now(timezone.utc).isoformat(),
              "path": str(path), "bytes": path.stat().st_size, "sha256": sha(path)}
    (OUT / f"source_{index}.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
    print(json.dumps(record), flush=True)


def sources() -> list[dict]:
    def job(i):
        manifest = OUT / f"source_{i}.json"
        if manifest.exists():
            data = json.loads(manifest.read_text())
            if Path(data["path"]).exists() and sha(Path(data["path"])) == data["sha256"]:
                return data
        bounded([sys.executable, str(Path(__file__).resolve()), "--download-one", str(i)], f"source_download_{i}")
        return json.loads(manifest.read_text())
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        data = list(pool.map(job, range(3)))
    (OUT / "sources.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    return data


def extract(path: Path, output: Path, filter_text: str, stage: str, *, seek: float | None = None, duration: float | None = None):
    if output.exists() and output.stat().st_size:
        return
    cmd = ["ffmpeg", "-v", "error", "-nostdin", "-n"]
    if seek is not None:
        cmd += ["-ss", str(max(0, seek))]
    cmd += ["-i", str(path)]
    if duration is not None:
        cmd += ["-t", str(duration)]
    cmd += ["-an", "-vf", filter_text, "-pix_fmt", "gray", "-f", "rawvideo", str(output)]
    bounded(cmd, stage)


def match(data: list[dict], parent: Path):
    import numpy as np
    # 192x108 preserves the source-frame aspect; 108x192 is full-cover geometry.
    source_arrays = {}
    for i, item in enumerate(data):
        for mode, vf, shape in (
            ("contain_safe_area", "fps=2,scale=192:108", (108,192)),
            ("cover", "fps=2,crop=ih*9/16:ih,scale=108:192", (192,108)),
        ):
            path = OUT / f"source_{i}_{mode}_2fps.gray"
            extract(Path(item["path"]), path, vf, f"index_{i}_{mode}")
            source_arrays[i, mode] = np.fromfile(path, dtype=np.uint8).reshape(-1,*shape)
    parent_raw = OUT / "parent_30fps.gray"
    extract(parent, parent_raw, "scale=216:384", "index_parent")
    frames = np.fromfile(parent_raw, dtype=np.uint8).reshape(-1,384,216)
    results = []
    from PIL import Image
    for beat, start in enumerate(STARTS):
        target_time = start + 0.6
        frame = frames[min(len(frames)-1, round(target_time*30))]
        target_full = np.asarray(Image.fromarray(frame).resize((108,192))).astype(np.float32)
        target_contain = np.asarray(Image.fromarray(frame[30:152]).resize((192,108))).astype(np.float32)
        options = []
        for (i,mode), arr in source_arrays.items():
            target = target_contain if mode == "contain_safe_area" else target_full
            # Caption band excluded in cover mode; contain crop contains no Jarvis captions.
            if mode == "cover":
                arr_masked = arr[:, :90, :]
                target = target[:90]
            else:
                arr_masked = arr
            delta = arr_masked.astype(np.float32) - target
            errors = np.mean(delta*delta, axis=(1,2))
            order = np.argsort(errors)[:3]
            options.extend({"source_index": i, "nasa_id": data[i]["nasa_id"],
                            "presentation_mode": mode, "source_time": float(j*.5),
                            "source_window_start": float(j*.5-.6),
                            "mse": float(errors[j])} for j in order)
        options.sort(key=lambda x:x["mse"])
        row = {"beat": beat+1, "timeline_start":start, "target_time": target_time,
               "best": options[0], "alternatives": options[1:4]}
        print(json.dumps(row), flush=True)
        results.append(row)
    (OUT / "coarse_matches.json").write_text(json.dumps({"parent":str(parent), "parent_sha256":sha(parent),
          "source_index_fps":2,"claim":"Pixel lineage recovery only, not new OpenCLIP approvals", "beats":results},indent=2),encoding="utf-8")


if __name__ == "__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--download-one", type=int)
    parser.add_argument("--download-only", action="store_true")
    parser.add_argument("--parent", type=Path, default=ROOT.parent/"Rich_V1_R13.mp4")
    args=parser.parse_args()
    OUT.mkdir(parents=True,exist_ok=True)
    if args.download_one is not None:
        download_one(args.download_one)
    else:
        records=sources()
        if not args.download_only:
            match(records,args.parent)
