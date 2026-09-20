from pathlib import Path
import inspect

from backend.services.pipelines.video_pipeline import VideoPipeline
from backend.services.video_renderer.renderer import VideoRenderer
from backend.services.video.source_clip_indexer import SourceClipIndexer

pipeline_source = Path(
    "backend/services/pipelines/video_pipeline.py"
).read_text(encoding="utf-8")

renderer_source = Path(
    "backend/services/video_renderer/renderer.py"
).read_text(encoding="utf-8")

checks = {
    "pipeline_v6_marker":
        "RICH_V1_VIDEO_BEATS_V6" in pipeline_source,

    "renderer_v6_marker":
        "RICH_V1_VIDEO_BEATS_V6" in renderer_source,

    "indexer_import":
        "SourceClipIndexer" in pipeline_source,

    "video_candidate_builder":
        "_v6_build_video_beat_candidates"
        in pipeline_source,

    "renderer_receives_video_beats":
        "beat_videos=" in pipeline_source,

    "renderer_signature_video_beats":
        "beat_videos" in str(
            inspect.signature(
                VideoRenderer.render
            )
        ),

    "video_file_clip":
        "VideoFileClip" in renderer_source,

    "exact_subclip":
        "start_time" in renderer_source
        and "end_time" in renderer_source
        and ".subclipped(" in renderer_source,

    "source_audio_removed":
        ".without_audio()" in renderer_source,

    "image_fallback_preserved":
        "beat_images" in renderer_source,

    "rights_media_groups_preserved":
        "media_groups=media_groups"
        in pipeline_source,
}

failed = [
    name
    for name, passed in checks.items()
    if not passed
]

print("=== RICH V1 V6 VERIFIER ===")

for name, passed in checks.items():
    print(
        f"{name}: "
        f"{'PASS' if passed else 'FAIL'}"
    )

if failed:
    raise SystemExit(
        "FAILED: " + ", ".join(failed)
    )

print("V6 STRUCTURAL VERIFIER: PASS")
