from __future__ import annotations

from pathlib import Path
from datetime import datetime
import py_compile
import shutil
import sys
import traceback

ROOT = Path.cwd()

PIPELINE = ROOT / "backend/services/pipelines/video_pipeline.py"
RENDERER = ROOT / "backend/services/video_renderer/renderer.py"

STAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
BACKUP = ROOT / "generated/diagnostics" / f"v6_real_{STAMP}" / "backup"
BACKUP.mkdir(parents=True, exist_ok=True)

PIPELINE_BACKUP = BACKUP / "video_pipeline.py"
RENDERER_BACKUP = BACKUP / "renderer.py"

MARKER = "RICH_V1_REAL_VIDEO_V6"

def compile_file(path: Path):
    py_compile.compile(
        str(path),
        doraise=True,
    )

def restore():
    if PIPELINE_BACKUP.exists():
        shutil.copy2(
            PIPELINE_BACKUP,
            PIPELINE,
        )

    if RENDERER_BACKUP.exists():
        shutil.copy2(
            RENDERER_BACKUP,
            RENDERER,
        )

def require_once(text, needle, label):
    count = text.count(needle)

    if count != 1:
        raise RuntimeError(
            f"{label}: expected exactly 1 occurrence "
            f"but found {count}"
        )

def replace_once(text, old, new, label):
    require_once(
        text,
        old,
        label,
    )

    return text.replace(
        old,
        new,
        1,
    )

print("============================================================")
print(" RICH V1 — REAL VIDEO V6 INSTALLER")
print("============================================================")
print()

# ------------------------------------------------------------
# 0. Verify current source before touching anything.
# ------------------------------------------------------------

compile_file(PIPELINE)
compile_file(RENDERER)

print("PRE-INSTALL COMPILE: PASS")

shutil.copy2(
    PIPELINE,
    PIPELINE_BACKUP,
)

shutil.copy2(
    RENDERER,
    RENDERER_BACKUP,
)

print(f"Backup: {BACKUP}")
print()

try:
    pipeline = PIPELINE.read_text(
        encoding="utf-8"
    )

    renderer = RENDERER.read_text(
        encoding="utf-8"
    )

    if MARKER in pipeline or MARKER in renderer:
        raise RuntimeError(
            "V6 is already installed. "
            "Refusing duplicate patch."
        )

    # ========================================================
    # PIPELINE
    # ========================================================

    # --------------------------------------------------------
    # 1. Imports
    # --------------------------------------------------------

    class_anchor = "class VideoPipeline"

    class_pos = pipeline.find(
        class_anchor
    )

    if class_pos < 0:
        raise RuntimeError(
            "VideoPipeline class anchor missing."
        )

    pipeline_imports = f'''
# {MARKER}
from backend.services.video.source_clip_indexer import SourceClipIndexer
from backend.services.video.strict_clip_matcher import StrictClipMatcher
from backend.services.video.visual_beat_source_planner import (
    SourceVisualBeat,
)

'''

    pipeline = (
        pipeline[:class_pos]
        + pipeline_imports
        + pipeline[class_pos:]
    )

    # --------------------------------------------------------
    # 2. Add helper methods immediately before run().
    # --------------------------------------------------------

    run_anchor = "\n    async def run("

    run_pos = pipeline.find(
        run_anchor,
        class_pos,
    )

    if run_pos < 0:
        raise RuntimeError(
            "VideoPipeline.run anchor missing."
        )

    helper = f'''
    # ========================================================
    # {MARKER}
    # ========================================================

    @staticmethod
    def _v6_source_beat(
        beat,
        beat_index: int,
    ):
        """
        Convert the existing VisualBeat into the concrete
        SourceVisualBeat consumed by StrictClipMatcher.

        Fail-soft by design: if the current source planner model
        differs, V5 image rendering remains available.
        """

        beat_id = str(
            getattr(
                beat,
                "beat_id",
                f"beat_{{beat_index + 1}}",
            )
        )

        visual_goal = str(
            getattr(
                beat,
                "visual_requirement",
                "",
            )
            or getattr(
                beat,
                "purpose",
                "",
            )
            or getattr(
                beat,
                "search_query",
                "",
            )
        ).strip()

        query = str(
            getattr(
                beat,
                "search_query",
                "",
            )
            or visual_goal
        ).strip()

        # Inspect the actual SourceVisualBeat dataclass fields.
        # This avoids coupling V6 to assumptions about fields
        # not present in the current repository version.
        import dataclasses

        fields = {{
            field.name
            for field
            in dataclasses.fields(
                SourceVisualBeat
            )
        }}

        values = {{}}

        if "beat_id" in fields:
            values["beat_id"] = beat_id

        if "visual_goal" in fields:
            values["visual_goal"] = visual_goal

        if "search_queries" in fields:
            values["search_queries"] = (
                [query]
                if query
                else [visual_goal]
            )

        if "negative_visuals" in fields:
            negative = getattr(
                beat,
                "negative_visuals",
                None,
            )

            if negative is None:
                negative = [
                    "generic stock footage",
                    "unrelated creator talking to camera",
                    "irrelevant lifestyle footage",
                ]

            values["negative_visuals"] = list(
                negative
            )

        # Preserve any matching fields already present on beat.
        for field_name in fields:
            if field_name in values:
                continue

            if hasattr(
                beat,
                field_name,
            ):
                values[field_name] = getattr(
                    beat,
                    field_name,
                )

        try:
            return SourceVisualBeat(
                **values
            )

        except Exception:
            return None


    def _v6_match_video_beats(
        self,
        *,
        media_groups,
        visual_beats,
        content_id: str,
    ):
        """
        authorized videos
            -> SourceClipIndexer
            -> StrictClipMatcher
            -> exact source timestamps

        Any failure returns [] and leaves V5 images untouched.
        """

        authorized_videos = []
        seen = set()

        for group in media_groups:

            for asset in group:

                if (
                    getattr(
                        asset,
                        "asset_type",
                        "",
                    )
                    != "video"
                ):
                    continue

                path = str(
                    getattr(
                        asset,
                        "file_path",
                        "",
                    )
                    or ""
                ).strip()

                if not path:
                    continue

                identity = str(
                    getattr(
                        asset,
                        "asset_id",
                        "",
                    )
                    or path
                )

                if identity in seen:
                    continue

                seen.add(identity)
                authorized_videos.append(
                    asset
                )

        if not authorized_videos:
            return {{
                "status": "fallback_images",
                "reason": "no_authorized_video_assets",
                "indexed_clips": 0,
                "matches": [],
            }}

        try:
            indexer = SourceClipIndexer()

            clips = indexer.index_assets(
                assets=authorized_videos,
                content_id=content_id,
            )

        except Exception as exc:
            return {{
                "status": "fallback_images",
                "reason": (
                    "clip_index_failed:"
                    + type(exc).__name__
                ),
                "indexed_clips": 0,
                "matches": [],
            }}

        if not clips:
            return {{
                "status": "fallback_images",
                "reason": "no_indexed_video_clips",
                "indexed_clips": 0,
                "matches": [],
            }}

        source_beats = []
        source_beat_indexes = []

        for beat_index, beat in enumerate(
            visual_beats
        ):

            converted = self._v6_source_beat(
                beat,
                beat_index,
            )

            if converted is None:
                continue

            source_beats.append(
                converted
            )

            source_beat_indexes.append(
                beat_index
            )

        if not source_beats:
            return {{
                "status": "fallback_images",
                "reason": "source_beat_conversion_failed",
                "indexed_clips": len(clips),
                "matches": [],
            }}

        try:
            matcher = StrictClipMatcher()

            matched = matcher.match_many(
                beats=source_beats,
                clips=clips,

                # Deliberately much stricter than the class
                # default of 10. Benchmarks need diversity.
                max_reuse_per_source=3,
            )

        except Exception as exc:
            return {{
                "status": "fallback_images",
                "reason": (
                    "strict_match_failed:"
                    + type(exc).__name__
                ),
                "indexed_clips": len(clips),
                "matches": [],
            }}

        if not matched:
            return {{
                "status": "fallback_images",
                "reason": "strict_match_no_winners",
                "indexed_clips": len(clips),
                "matches": [],
            }}

        beat_index_by_id = {{}}

        for index, source_beat in zip(
            source_beat_indexes,
            source_beats,
        ):
            beat_index_by_id[
                str(source_beat.beat_id)
            ] = index

        output = []

        for match in matched:

            beat_index = (
                beat_index_by_id.get(
                    str(match.beat_id)
                )
            )

            if beat_index is None:
                continue

            output.append(
                {{
                    "beat_index": beat_index,
                    "beat_id": match.beat_id,
                    "visual_goal": (
                        match.visual_goal
                    ),
                    "clip_id": match.clip_id,
                    "source_path": (
                        match.source_path
                    ),
                    "source_name": (
                        match.source_name
                    ),
                    "start_time": float(
                        match.start_time
                    ),
                    "end_time": float(
                        match.end_time
                    ),
                    "duration": float(
                        match.duration
                    ),
                    "preview_path": (
                        match.preview_path
                    ),
                    "positive_score": float(
                        match.positive_score
                    ),
                    "negative_score": float(
                        match.negative_score
                    ),
                    "final_score": float(
                        match.final_score
                    ),
                }}
            )

        return {{
            "status": (
                "video_matches_ready"
                if output
                else "fallback_images"
            ),
            "reason": (
                "strict_semantic_matches"
                if output
                else "matches_lost_during_mapping"
            ),
            "authorized_video_assets": (
                len(authorized_videos)
            ),
            "indexed_clips": len(clips),
            "matches": output,
        }}

'''

    pipeline = (
        pipeline[:run_pos]
        + "\n"
        + helper
        + pipeline[run_pos:]
    )

    # --------------------------------------------------------
    # 3. Build video matches immediately before the existing
    #    production package.
    #
    # Exact current anchor from production:
    # package = await self.package_builder.build(...)
    # --------------------------------------------------------

    package_anchor = (
        "        package = await "
        "self.package_builder.build(\n"
    )

    require_once(
        pipeline,
        package_anchor,
        "package build anchor",
    )

    video_match_block = f'''
        # ====================================================
        # {MARKER}
        # Build semantic moving-footage matches.
        #
        # Existing beat_render_assets remain intact and are
        # therefore the fallback for every unmatched beat.
        # ====================================================

        v6_video_result = (
            self._v6_match_video_beats(
                media_groups=media_groups,
                visual_beats=visual_beats,
                content_id=str(
                    content_id
                ),
            )
        )

        v6_video_matches = (
            v6_video_result.get(
                "matches",
                []
            )
        )

'''

    pipeline = replace_once(
        pipeline,
        package_anchor,
        video_match_block
        + package_anchor,
        "insert V6 matching",
    )

    # --------------------------------------------------------
    # 4. Pass exact video matches into renderer.
    # --------------------------------------------------------

    render_anchor = (
        "            beat_images="
        "beat_render_assets,\n"
    )

    pipeline = replace_once(
        pipeline,
        render_anchor,
        render_anchor
        + (
            "            beat_videos="
            "v6_video_matches,\n"
        ),
        "renderer video argument",
    )

    # --------------------------------------------------------
    # 5. Return evidence.
    # --------------------------------------------------------

    evidence_anchor = (
        '            "visual_beats": '
        'visual_beat_dicts,\n'
    )

    pipeline = replace_once(
        pipeline,
        evidence_anchor,
        evidence_anchor
        + (
            '            "v6_video_matching": '
            'v6_video_result,\n'
        ),
        "V6 evidence",
    )

    # ========================================================
    # RENDERER
    # ========================================================

    # --------------------------------------------------------
    # 6. MoviePy VideoFileClip import.
    # --------------------------------------------------------

    if "VideoFileClip" not in renderer:

        moviepy_anchor = (
            "from moviepy import ("
        )

        require_once(
            renderer,
            moviepy_anchor,
            "MoviePy import",
        )

        renderer = replace_once(
            renderer,
            moviepy_anchor,
            moviepy_anchor
            + "\n    VideoFileClip,",
            "VideoFileClip import",
        )

    # --------------------------------------------------------
    # 7. Add beat_videos to existing render signature.
    # --------------------------------------------------------

    beat_images_anchor = (
        "        beat_images: "
        "list[GeneratedImage] | None = None,\n"
    )

    renderer = replace_once(
        renderer,
        beat_images_anchor,
        beat_images_anchor
        + (
            "        beat_videos: "
            "list[dict] | None = None,  "
            f"# {MARKER}\n"
        ),
        "renderer signature",
    )

    # --------------------------------------------------------
    # 8. Create lookup once.
    # --------------------------------------------------------

    image_clips_anchor = (
        "        image_clips = []"
    )

    require_once(
        renderer,
        image_clips_anchor,
        "image_clips init",
    )

    renderer = replace_once(
        renderer,
        image_clips_anchor,
        image_clips_anchor
        + f'''

        # {MARKER}
        video_sources = []

        beat_video_lookup = {{
            int(item.get("beat_index", -1)): item
            for item in (beat_videos or [])
            if isinstance(item, dict)
        }}
''',
        "video lookup init",
    )

    # --------------------------------------------------------
    # 9. Locate semantic beat append.
    #
    # We do NOT delete or bypass the existing image code.
    # The existing image clip is built normally first.
    # Immediately before append, V6 can replace that local
    # clip variable with a real video segment.
    # --------------------------------------------------------

    semantic_pos = renderer.find(
        "            if use_semantic_beats:"
    )

    if semantic_pos < 0:
        raise RuntimeError(
            "use_semantic_beats block missing."
        )

    append_pos = renderer.find(
        "image_clips.append(",
        semantic_pos,
    )

    if append_pos < 0:
        raise RuntimeError(
            "semantic image_clips.append missing."
        )

    append_end = renderer.find(
        "\n",
        append_pos,
    )

    if append_end < 0:
        raise RuntimeError(
            "append line end missing."
        )

    append_line_start = (
        renderer.rfind(
            "\n",
            semantic_pos,
            append_pos,
        )
        + 1
    )

    append_line = renderer[
        append_line_start:
        append_end
    ]

    import re

    variable_match = re.search(
        r"image_clips\.append\(\s*"
        r"([A-Za-z_][A-Za-z0-9_]*)",
        append_line,
    )

    if variable_match is None:
        # Some versions format append across lines.
        append_window = renderer[
            append_pos:
            min(
                len(renderer),
                append_pos + 250,
            )
        ]

        variable_match = re.search(
            r"image_clips\.append\(\s*"
            r"([A-Za-z_][A-Za-z0-9_]*)",
            append_window,
        )

    if variable_match is None:
        raise RuntimeError(
            "Could not identify semantic clip variable."
        )

    clip_variable = (
        variable_match.group(1)
    )

    indent = append_line[
        :len(append_line)
        - len(append_line.lstrip())
    ]

    override = f'''
{{indent}}# {MARKER}
{{indent}}# Prefer an exact semantically matched source-video
{{indent}}# segment. Existing image clip remains the fallback.
{{indent}}video_spec = beat_video_lookup.get(
{{indent}}    beat_index
{{indent}})
{{indent}}
{{indent}}if video_spec is not None:
{{indent}}    source_path = Path(
{{indent}}        str(
{{indent}}            video_spec.get(
{{indent}}                "source_path",
{{indent}}                "",
{{indent}}            )
{{indent}}        )
{{indent}}    )
{{indent}}
{{indent}}    if source_path.exists():
{{indent}}        try:
{{indent}}            source_video = VideoFileClip(
{{indent}}                str(source_path)
{{indent}}            )
{{indent}}
{{indent}}            video_sources.append(
{{indent}}                source_video
{{indent}}            )
{{indent}}
{{indent}}            start_time = max(
{{indent}}                0.0,
{{indent}}                float(
{{indent}}                    video_spec.get(
{{indent}}                        "start_time",
{{indent}}                        0.0,
{{indent}}                    )
{{indent}}                ),
{{indent}}            )
{{indent}}
{{indent}}            end_time = min(
{{indent}}                float(
{{indent}}                    source_video.duration
{{indent}}                ),
{{indent}}                float(
{{indent}}                    video_spec.get(
{{indent}}                        "end_time",
{{indent}}                        start_time
{{indent}}                        + cut_duration,
{{indent}}                    )
{{indent}}                ),
{{indent}}            )
{{indent}}
{{indent}}            if end_time > start_time:
{{indent}}                moving_clip = (
{{indent}}                    source_video
{{indent}}                    .subclipped(
{{indent}}                        start_time,
{{indent}}                        end_time,
{{indent}}                    )
{{indent}}                    .without_audio()
{{indent}}                )
{{indent}}
{{indent}}                # Keep the narration-driven beat
{{indent}}                # duration from the production
{{indent}}                # renderer. If indexed footage is
{{indent}}                # longer, trim it. If shorter, use
{{indent}}                # the available source segment rather
{{indent}}                # than fabricating a frozen frame.
{{indent}}                target_duration = min(
{{indent}}                    float(cut_duration),
{{indent}}                    float(
{{indent}}                        moving_clip.duration
{{indent}}                    ),
{{indent}}                )
{{indent}}
{{indent}}                if target_duration > 0.05:
{{indent}}                    moving_clip = (
{{indent}}                        moving_clip.subclipped(
{{indent}}                            0,
{{indent}}                            target_duration,
{{indent}}                        )
{{indent}}                    )
{{indent}}
{{indent}}                    moving_clip = (
{{indent}}                        self._fit_visual(
{{indent}}                            moving_clip,
{{indent}}                            target_duration,
{{indent}}                        )
{{indent}}                    )
{{indent}}
{{indent}}                    {{clip_variable}} = (
{{indent}}                        moving_clip
{{indent}}                    )
{{indent}}
{{indent}}        except Exception:
{{indent}}            # Per-beat fail-soft fallback.
{{indent}}            # The image clip already exists.
{{indent}}            pass
{{indent}}
'''

    renderer = (
        renderer[:append_line_start]
        + override
        + renderer[append_line_start:]
    )

    # --------------------------------------------------------
    # 10. Cleanup VideoFileClip resources.
    # --------------------------------------------------------

    cleanup_anchor = (
        "            for clip in image_clips:"
    )

    require_once(
        renderer,
        cleanup_anchor,
        "renderer cleanup",
    )

    renderer = replace_once(
        renderer,
        cleanup_anchor,
        f'''            # {MARKER}
            for source_video in video_sources:
                try:
                    source_video.close()
                except Exception:
                    pass

'''
        + cleanup_anchor,
        "video cleanup",
    )

    # ========================================================
    # WRITE
    # ========================================================

    PIPELINE.write_text(
        pipeline,
        encoding="utf-8",
    )

    RENDERER.write_text(
        renderer,
        encoding="utf-8",
    )

    # ========================================================
    # COMPILE
    # ========================================================

    compile_file(PIPELINE)
    compile_file(RENDERER)

    print("POST-INSTALL COMPILE: PASS")

    # ========================================================
    # IMPORT VERIFICATION
    # ========================================================

    from backend.services.pipelines.video_pipeline import VideoPipeline
    from backend.services.video_renderer.renderer import VideoRenderer
    from backend.services.video.source_clip_indexer import SourceClipIndexer
    from backend.services.video.strict_clip_matcher import StrictClipMatcher

    import inspect

    signature = str(
        inspect.signature(
            VideoRenderer.render
        )
    )

    checks = {
        "pipeline_marker":
            MARKER in PIPELINE.read_text(
                encoding="utf-8"
            ),

        "renderer_marker":
            MARKER in RENDERER.read_text(
                encoding="utf-8"
            ),

        "indexer_import":
            SourceClipIndexer is not None,

        "strict_matcher_import":
            StrictClipMatcher is not None,

        "pipeline_helper":
            hasattr(
                VideoPipeline,
                "_v6_match_video_beats",
            ),

        "renderer_accepts_beat_videos":
            "beat_videos" in signature,

        "image_fallback_preserved":
            "beat_images" in signature,
    }

    print()
    print("=== V6 VERIFIER ===")

    failed = []

    for name, passed in checks.items():
        print(
            f"{name}: "
            f"{'PASS' if passed else 'FAIL'}"
        )

        if not passed:
            failed.append(name)

    if failed:
        raise RuntimeError(
            "V6 verification failed: "
            + ", ".join(failed)
        )

    print()
    print("============================================================")
    print(" V6 INSTALL: PASS")
    print("============================================================")
    print()
    print(
        "Next step: controlled V6 benchmark render."
    )

except Exception:
    print()
    print("============================================================")
    print(" V6 INSTALL FAILED — ROLLING BACK")
    print("============================================================")
    print()

    traceback.print_exc()

    restore()

    try:
        compile_file(PIPELINE)
        compile_file(RENDERER)
        print()
        print("ROLLBACK COMPILE: PASS")
    except Exception:
        print()
        print("WARNING: rollback compile failed")
        traceback.print_exc()

    print()
    print(
        "Original production files restored from:"
    )
    print(BACKUP)

    sys.exit(1)
