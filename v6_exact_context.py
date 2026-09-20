from pathlib import Path

FILES = {
    "PIPELINE": Path(
        "backend/services/pipelines/video_pipeline.py"
    ),
    "RENDERER": Path(
        "backend/services/video_renderer/renderer.py"
    ),
}

def dump_range(lines, start, end):
    start = max(1, start)
    end = min(len(lines), end)

    for n in range(start, end + 1):
        print(f"{n}: {lines[n - 1]}")

def contexts(lines, needles, before=20, after=45):
    found = set()

    for needle in needles:
        for i, line in enumerate(lines, start=1):
            if needle.lower() in line.lower():
                lo = max(1, i - before)
                hi = min(len(lines), i + after)

                key = (lo, hi)

                if key in found:
                    continue

                found.add(key)

                print()
                print("=" * 72)
                print(f"MATCH: {needle!r} @ LINE {i}")
                print("=" * 72)

                dump_range(lines, lo, hi)

for label, path in FILES.items():

    print()
    print("#" * 80)
    print(f"# {label}: {path}")
    print("#" * 80)

    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()

    print(f"TOTAL_LINES: {len(lines)}")

    if label == "PIPELINE":

        contexts(
            lines,
            [
                "class VideoPipeline",
                "async def run(",
                "media_groups",
                "beat_render_assets",
                "Temporary renderer compatibility",
                "package = await self.package_builder.build",
                "video = await self.renderer.render",
                "beat_images=beat_render_assets",
            ],
            before=18,
            after=55,
        )

    else:

        contexts(
            lines,
            [
                "from moviepy import",
                "async def render(",
                "beat_images:",
                "use_semantic_beats",
                "for beat_index",
                "ImageClip(",
                "image_clips.append",
                "_cover_image_clip",
                "_fit_visual",
                "finally:",
                "for clip in image_clips",
            ],
            before=18,
            after=60,
        )

print()
print("=" * 80)
print("IMPORT TESTS")
print("=" * 80)

try:
    from backend.services.video.source_clip_indexer import SourceClipIndexer
    print("SourceClipIndexer import: PASS")
except Exception as exc:
    print(
        "SourceClipIndexer import: FAIL",
        type(exc).__name__,
        str(exc),
    )

try:
    from backend.services.video_renderer.renderer import VideoRenderer
    print("VideoRenderer import: PASS")
except Exception as exc:
    print(
        "VideoRenderer import: FAIL",
        type(exc).__name__,
        str(exc),
    )

print()
print("DIAGNOSTIC COMPLETE")
