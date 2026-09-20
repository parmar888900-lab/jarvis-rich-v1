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

BACKUP_DIR = (
    ROOT
    / "generated"
    / "diagnostics"
    / f"v6_fixed_{STAMP}"
    / "backup"
)

BACKUP_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

PIPELINE_BACKUP = (
    BACKUP_DIR / "video_pipeline.py"
)

RENDERER_BACKUP = (
    BACKUP_DIR / "renderer.py"
)

MARKER = "RICH_V1_REAL_VIDEO_V6_FIXED"


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


def require_once(
    text: str,
    needle: str,
    label: str,
):
    count = text.count(needle)

    if count != 1:
        raise RuntimeError(
            f"{label}: expected 1 occurrence, "
            f"found {count}"
        )


def replace_once(
    text: str,
    old: str,
    new: str,
    label: str,
):
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


print("=" * 64)
print(" RICH V1 — V6 REAL VIDEO FIXED INSTALLER")
print("=" * 64)
print()

# ============================================================
# 0. BASELINE
# ============================================================

compile_file(PIPELINE)
compile_file(RENDERER)

print("BASELINE COMPILE: PASS")

shutil.copy2(
    PIPELINE,
    PIPELINE_BACKUP,
)

shutil.copy2(
    RENDERER,
    RENDERER_BACKUP,
)

print(
    "BACKUP:",
    BACKUP_DIR,
)

try:

    pipeline = PIPELINE.read_text(
        encoding="utf-8"
    )

    renderer = RENDERER.read_text(
        encoding="utf-8"
    )

    if MARKER in pipeline:
        raise RuntimeError(
            "V6 FIXED already appears installed "
            "in video_pipeline.py"
        )

    if MARKER in renderer:
        raise RuntimeError(
            "V6 FIXED already appears installed "
            "in renderer.py"
        )

    # ========================================================
    # 1. PIPELINE IMPORTS
    # ========================================================

    pipeline_class_anchor = (
        "class VideoPipeline:"
    )

    require_once(
        pipeline,
        pipeline_class_anchor,
        "VideoPipeline class",
    )

    pipeline_imports = '''
# RICH_V1_REAL_VIDEO_V6_FIXED
from backend.services.video.source_clip_indexer import (
    SourceClipIndexer,
)
from backend.services.video.strict_clip_matcher import (
    StrictClipMatcher,
)
from backend.services.video.visual_beat_source_planner import (
    SourceVisualBeat,
)


'''

    pipeline = replace_once(
        pipeline,
        pipeline_class_anchor,
        pipeline_imports
        + pipeline_class_anchor,
        "V6 pipeline imports",
    )

    # ========================================================
    # 2. PIPELINE V6 HELPERS
    # ========================================================

    run_anchor = (
        "    async def run(\n"
    )

    require_once(
        pipeline,
        run_anchor,
        "VideoPipeline.run",
    )

    helper_code = '''
    # ========================================================
    # RICH_V1_REAL_VIDEO_V6_FIXED
    # Real-video semantic matching layer.
    #
    # This layer is fail-soft. Existing V5 images remain the
    # fallback whenever video indexing/matching is unavailable.
    # ========================================================

    @staticmethod
    def _v6_make_source_beat(
        beat,
        beat_index: int,
    ):
        import dataclasses

        try:
            field_names = {
                field.name
                for field
                in dataclasses.fields(
                    SourceVisualBeat
                )
            }
        except Exception:
            return None

        beat_id = str(
            getattr(
                beat,
                "beat_id",
                f"beat_{beat_index + 1}",
            )
        ).strip()

        visual_goal = str(
            getattr(
                beat,
                "visual_goal",
                "",
            )
            or getattr(
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

        search_query = str(
            getattr(
                beat,
                "search_query",
                "",
            )
            or visual_goal
        ).strip()

        values = {}

        if "beat_id" in field_names:
            values["beat_id"] = beat_id

        if "visual_goal" in field_names:
            values["visual_goal"] = (
                visual_goal
            )

        if "search_queries" in field_names:
            values["search_queries"] = [
                search_query
            ]

        if "negative_visuals" in field_names:

            negative = getattr(
                beat,
                "negative_visuals",
                None,
            )

            if not negative:
                negative = [
                    "generic stock footage",
                    "unrelated person talking",
                    "irrelevant lifestyle footage",
                    "unrelated product footage",
                ]

            values[
                "negative_visuals"
            ] = list(negative)

        # Copy any identically named fields that exist on the
        # current VisualBeat model.
        for field_name in field_names:

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


    def _v6_build_video_matches(
        self,
        *,
        media_groups,
        visual_beats,
        content_id: str,
    ) -> dict:

        authorized_videos = []
        seen_assets = set()

        # ----------------------------------------------------
        # Collect only media already authorized upstream.
        # ----------------------------------------------------

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

                file_path = str(
                    getattr(
                        asset,
                        "file_path",
                        "",
                    )
                    or ""
                ).strip()

                if not file_path:
                    continue

                identity = str(
                    getattr(
                        asset,
                        "asset_id",
                        "",
                    )
                    or file_path
                )

                if identity in seen_assets:
                    continue

                seen_assets.add(
                    identity
                )

                authorized_videos.append(
                    asset
                )

        if not authorized_videos:

            return {
                "status":
                    "fallback_images",

                "reason":
                    "no_authorized_video_assets",

                "authorized_video_assets":
                    0,

                "indexed_clips":
                    0,

                "matches":
                    [],
            }

        # ----------------------------------------------------
        # Break source videos into selectable moments.
        # ----------------------------------------------------

        try:

            indexer = (
                SourceClipIndexer()
            )

            indexed_clips = (
                indexer.index_assets(
                    assets=(
                        authorized_videos
                    ),
                    content_id=(
                        content_id
                    ),
                )
            )

        except Exception as exc:

            return {
                "status":
                    "fallback_images",

                "reason":
                    (
                        "indexer_failed:"
                        + type(exc).__name__
                    ),

                "authorized_video_assets":
                    len(
                        authorized_videos
                    ),

                "indexed_clips":
                    0,

                "matches":
                    [],
            }

        if not indexed_clips:

            return {
                "status":
                    "fallback_images",

                "reason":
                    "no_indexed_clips",

                "authorized_video_assets":
                    len(
                        authorized_videos
                    ),

                "indexed_clips":
                    0,

                "matches":
                    [],
            }

        # ----------------------------------------------------
        # Convert existing visual beats into SourceVisualBeat.
        # ----------------------------------------------------

        source_beats = []
        beat_indexes = {}

        for beat_index, beat in enumerate(
            visual_beats
        ):

            source_beat = (
                self._v6_make_source_beat(
                    beat,
                    beat_index,
                )
            )

            if source_beat is None:
                continue

            source_beats.append(
                source_beat
            )

            beat_indexes[
                str(
                    source_beat.beat_id
                )
            ] = beat_index

        if not source_beats:

            return {
                "status":
                    "fallback_images",

                "reason":
                    "source_beat_conversion_failed",

                "authorized_video_assets":
                    len(
                        authorized_videos
                    ),

                "indexed_clips":
                    len(
                        indexed_clips
                    ),

                "matches":
                    [],
            }

        # ----------------------------------------------------
        # Strict positive/negative CLIP matching.
        # ----------------------------------------------------

        try:

            matcher = (
                StrictClipMatcher()
            )

            matches = (
                matcher.match_many(
                    beats=source_beats,
                    clips=indexed_clips,

                    # Benchmarks need source diversity.
                    max_reuse_per_source=3,
                )
            )

        except Exception as exc:

            return {
                "status":
                    "fallback_images",

                "reason":
                    (
                        "strict_matcher_failed:"
                        + type(exc).__name__
                    ),

                "authorized_video_assets":
                    len(
                        authorized_videos
                    ),

                "indexed_clips":
                    len(
                        indexed_clips
                    ),

                "matches":
                    [],
            }

        rendered_matches = []

        for match in matches:

            beat_index = (
                beat_indexes.get(
                    str(
                        match.beat_id
                    )
                )
            )

            if beat_index is None:
                continue

            rendered_matches.append(
                {
                    "beat_index":
                        int(
                            beat_index
                        ),

                    "beat_id":
                        str(
                            match.beat_id
                        ),

                    "visual_goal":
                        str(
                            match.visual_goal
                        ),

                    "clip_id":
                        str(
                            match.clip_id
                        ),

                    "source_path":
                        str(
                            match.source_path
                        ),

                    "source_name":
                        str(
                            match.source_name
                        ),

                    "start_time":
                        float(
                            match.start_time
                        ),

                    "end_time":
                        float(
                            match.end_time
                        ),

                    "duration":
                        float(
                            match.duration
                        ),

                    "positive_score":
                        float(
                            match.positive_score
                        ),

                    "negative_score":
                        float(
                            match.negative_score
                        ),

                    "final_score":
                        float(
                            match.final_score
                        ),
                }
            )

        return {
            "status":
                (
                    "video_matches_ready"
                    if rendered_matches
                    else "fallback_images"
                ),

            "reason":
                (
                    "strict_semantic_matches"
                    if rendered_matches
                    else "no_strict_matches"
                ),

            "authorized_video_assets":
                len(
                    authorized_videos
                ),

            "indexed_clips":
                len(
                    indexed_clips
                ),

            "matches":
                rendered_matches,
        }


'''

    pipeline = replace_once(
        pipeline,
        run_anchor,
        helper_code
        + run_anchor,
        "V6 helper insertion",
    )

    # ========================================================
    # 3. CREATE VIDEO MATCHES BEFORE PACKAGE BUILD
    # ========================================================

    package_anchor = (
        "        package = await "
        "self.package_builder.build(\n"
    )

    require_once(
        pipeline,
        package_anchor,
        "production package build",
    )

    matching_code = '''
        # ====================================================
        # RICH_V1_REAL_VIDEO_V6_FIXED
        # Build exact source-video assignments.
        # ====================================================

        v6_video_result = (
            self._v6_build_video_matches(
                media_groups=media_groups,
                visual_beats=visual_beats,
                content_id=str(
                    content_id
                ),
            )
        )

        v6_video_matches = list(
            v6_video_result.get(
                "matches",
                [],
            )
        )

'''

    pipeline = replace_once(
        pipeline,
        package_anchor,
        matching_code
        + package_anchor,
        "V6 match call",
    )

    # ========================================================
    # 4. PASS MATCHES TO RENDERER
    # ========================================================

    renderer_call_anchor = (
        "            beat_images="
        "beat_render_assets,\n"
    )

    require_once(
        pipeline,
        renderer_call_anchor,
        "beat_images renderer call",
    )

    pipeline = replace_once(
        pipeline,
        renderer_call_anchor,
        renderer_call_anchor
        + (
            "            beat_videos="
            "v6_video_matches,\n"
        ),
        "beat_videos renderer call",
    )

    # ========================================================
    # 5. RETURN V6 DIAGNOSTICS
    # ========================================================

    evidence_anchor = (
        '            "beat_media": '
        'beat_media_evidence,\n'
    )

    require_once(
        pipeline,
        evidence_anchor,
        "beat_media evidence",
    )

    pipeline = replace_once(
        pipeline,
        evidence_anchor,
        evidence_anchor
        + (
            '            "v6_video_matching": '
            'v6_video_result,\n'
        ),
        "V6 return evidence",
    )

    # ========================================================
    # 6. RENDERER — VideoFileClip import
    # ========================================================

    moviepy_anchor = (
        "    ImageClip,\n"
    )

    require_once(
        renderer,
        moviepy_anchor,
        "MoviePy ImageClip import",
    )

    renderer = replace_once(
        renderer,
        moviepy_anchor,
        moviepy_anchor
        + "    VideoFileClip,\n",
        "VideoFileClip import",
    )

    # ========================================================
    # 7. RENDERER — add beat_videos argument
    # ========================================================

    signature_anchor = (
        "        beat_images: "
        "list[GeneratedImage] | None = None,\n"
    )

    require_once(
        renderer,
        signature_anchor,
        "beat_images signature",
    )

    renderer = replace_once(
        renderer,
        signature_anchor,
        signature_anchor
        + (
            "        beat_videos: "
            "list[dict] | None = None,\n"
        ),
        "beat_videos signature",
    )

    # ========================================================
    # 8. VIDEO LOOKUP
    # ========================================================

    clips_init_anchor = (
        "        image_clips = []\n"
    )

    require_once(
        renderer,
        clips_init_anchor,
        "image_clips initialization",
    )

    lookup_code = '''
        # RICH_V1_REAL_VIDEO_V6_FIXED
        video_source_clips = []

        beat_video_lookup = {
            int(
                item.get(
                    "beat_index",
                    -1,
                )
            ): item
            for item
            in (beat_videos or [])
            if isinstance(
                item,
                dict,
            )
        }

'''

    renderer = replace_once(
        renderer,
        clips_init_anchor,
        clips_init_anchor
        + lookup_code,
        "V6 video lookup",
    )

    # ========================================================
    # 9. IDENTIFY SEMANTIC IMAGE APPEND STRUCTURALLY
    # ========================================================

    semantic_anchor = (
        "            if use_semantic_beats:"
    )

    semantic_start = renderer.find(
        semantic_anchor
    )

    if semantic_start < 0:
        raise RuntimeError(
            "Semantic beat rendering block "
            "not found."
        )

    # Search only inside the semantic rendering area.
    append_start = renderer.find(
        "image_clips.append(",
        semantic_start,
    )

    if append_start < 0:
        raise RuntimeError(
            "Semantic image_clips.append "
            "not found."
        )

    # Find beginning of physical line.
    append_line_start = (
        renderer.rfind(
            "\n",
            semantic_start,
            append_start,
        )
        + 1
    )

    # Determine actual indentation directly from source.
    line_end = renderer.find(
        "\n",
        append_line_start,
    )

    if line_end < 0:
        raise RuntimeError(
            "Could not determine append line."
        )

    first_line = renderer[
        append_line_start:
        line_end
    ]

    indentation = (
        first_line[
            :len(first_line)
            - len(
                first_line.lstrip()
            )
        ]
    )

    if not indentation:
        raise RuntimeError(
            "Semantic append indentation "
            "could not be determined."
        )

    # --------------------------------------------------------
    # Find the variable passed to image_clips.append(...).
    # --------------------------------------------------------

    import re

    append_window = renderer[
        append_start:
        min(
            len(renderer),
            append_start + 400,
        )
    ]

    variable_match = re.search(
        r"image_clips\.append"
        r"\(\s*"
        r"([A-Za-z_][A-Za-z0-9_]*)",
        append_window,
    )

    if variable_match is None:
        raise RuntimeError(
            "Could not identify rendered "
            "beat clip variable."
        )

    clip_variable = (
        variable_match.group(1)
    )

    # --------------------------------------------------------
    # Determine beat index variable.
    # Existing renderer diagnostic confirmed semantic beats
    # are rendered inside a beat-index loop.
    # --------------------------------------------------------

    loop_window_start = max(
        semantic_start,
        append_start - 8000,
    )

    loop_window = renderer[
        loop_window_start:
        append_start
    ]

    beat_loop_matches = list(
        re.finditer(
            r"for\s+"
            r"([A-Za-z_][A-Za-z0-9_]*)"
            r"\s*,\s*"
            r"([A-Za-z_][A-Za-z0-9_]*)"
            r"\s+in\s+enumerate\(",
            loop_window,
        )
    )

    if not beat_loop_matches:
        raise RuntimeError(
            "Could not identify semantic "
            "beat enumerate loop."
        )

    beat_index_variable = (
        beat_loop_matches[-1].group(1)
    )

    # --------------------------------------------------------
    # Find duration variable from local semantic block.
    # Prefer beat_duration; otherwise inspect set_duration /
    # with_duration calls.
    # --------------------------------------------------------

    local_window = renderer[
        max(
            semantic_start,
            append_start - 5000,
        ):
        append_start
    ]

    duration_variable = None

    for candidate in (
        "beat_duration",
        "cut_duration",
        "duration",
    ):
        if re.search(
            rf"\b{candidate}\b",
            local_window,
        ):
            duration_variable = candidate
            break

    if duration_variable is None:
        raise RuntimeError(
            "Could not identify semantic "
            "beat duration variable."
        )

    # ========================================================
    # 10. BUILD OVERRIDE USING REAL INDENTATION
    #
    # IMPORTANT:
    # This deliberately uses normal string concatenation.
    # There are NO literal {indent} placeholders.
    # ========================================================

    I = indentation
    II = I + "    "
    III = II + "    "
    IV = III + "    "
    V = IV + "    "
    VI = V + "    "

    override_lines = [
        I + "# RICH_V1_REAL_VIDEO_V6_FIXED",
        I + "# Replace the already-built image clip only when",
        I + "# StrictClipMatcher supplied a valid exact video segment.",
        I + "video_spec = beat_video_lookup.get(",
        II + beat_index_variable,
        I + ")",
        "",
        I + "if video_spec is not None:",
        II + "source_path = Path(",
        III + "str(",
        IV + "video_spec.get(",
        V + '"source_path",',
        V + '"",',
        IV + ")",
        III + ")",
        II + ")",
        "",
        II + "if source_path.exists():",
        III + "try:",
        IV + "source_video = VideoFileClip(",
        V + "str(source_path)",
        IV + ")",
        "",
        IV + "video_source_clips.append(",
        V + "source_video",
        IV + ")",
        "",
        IV + "start_time = max(",
        V + "0.0,",
        V + "float(",
        VI + "video_spec.get(",
        VI + '    "start_time",',
        VI + "    0.0,",
        VI + ")",
        V + "),",
        IV + ")",
        "",
        IV + "end_time = min(",
        V + "float(source_video.duration),",
        V + "float(",
        VI + "video_spec.get(",
        VI + '    "end_time",',
        VI + "    start_time",
        VI + "    + float(" + duration_variable + "),",
        VI + ")",
        V + "),",
        IV + ")",
        "",
        IV + "if end_time > start_time:",
        V + "moving_clip = (",
        VI + "source_video",
        VI + ".subclipped(",
        VI + "    start_time,",
        VI + "    end_time,",
        VI + ")",
        VI + ".without_audio()",
        V + ")",
        "",
        V + "available_duration = float(",
        VI + "moving_clip.duration",
        V + ")",
        "",
        V + "target_duration = min(",
        VI + "float(" + duration_variable + "),",
        VI + "available_duration,",
        V + ")",
        "",
        V + "if target_duration > 0.05:",
        VI + "moving_clip = (",
        VI + "    moving_clip.subclipped(",
        VI + "        0.0,",
        VI + "        target_duration,",
        VI + "    )",
        VI + ")",
        "",
        VI + "moving_clip = (",
        VI + "    self._fit_visual(",
        VI + "        moving_clip,",
        VI + "        target_duration,",
        VI + "    )",
        VI + ")",
        "",
        VI + clip_variable + " = moving_clip",
        "",
        III + "except Exception:",
        IV + "# Per-beat fail-soft fallback.",
        IV + "# Existing image clip remains unchanged.",
        IV + "pass",
        "",
    ]

    override_code = (
        "\n".join(
            override_lines
        )
        + "\n"
    )

    renderer = (
        renderer[:append_line_start]
        + override_code
        + renderer[append_line_start:]
    )

    # ========================================================
    # 11. CLOSE SOURCE VIDEO HANDLES
    # ========================================================

    cleanup_anchor = (
        "            for clip in image_clips:\n"
    )

    require_once(
        renderer,
        cleanup_anchor,
        "image clip cleanup",
    )

    cleanup_code = '''
            # RICH_V1_REAL_VIDEO_V6_FIXED
            for source_video in video_source_clips:
                try:
                    source_video.close()
                except Exception:
                    pass

'''

    renderer = replace_once(
        renderer,
        cleanup_anchor,
        cleanup_code
        + cleanup_anchor,
        "V6 source cleanup",
    )

    # ========================================================
    # 12. WRITE
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
    # 13. COMPILE
    # ========================================================

    compile_file(PIPELINE)
    compile_file(RENDERER)

    print(
        "PATCHED SOURCE COMPILE: PASS"
    )

    # ========================================================
    # 14. IMPORT VERIFICATION
    # ========================================================

    from backend.services.pipelines.video_pipeline import (
        VideoPipeline,
    )

    from backend.services.video_renderer.renderer import (
        VideoRenderer,
    )

    from backend.services.video.source_clip_indexer import (
        SourceClipIndexer,
    )

    from backend.services.video.strict_clip_matcher import (
        StrictClipMatcher,
    )

    import inspect

    render_signature = str(
        inspect.signature(
            VideoRenderer.render
        )
    )

    checks = {
        "pipeline_marker":
            MARKER
            in PIPELINE.read_text(
                encoding="utf-8"
            ),

        "renderer_marker":
            MARKER
            in RENDERER.read_text(
                encoding="utf-8"
            ),

        "pipeline_helper":
            hasattr(
                VideoPipeline,
                "_v6_build_video_matches",
            ),

        "source_indexer":
            SourceClipIndexer
            is not None,

        "strict_matcher":
            StrictClipMatcher
            is not None,

        "renderer_beat_videos":
            "beat_videos"
            in render_signature,

        "renderer_image_fallback":
            "beat_images"
            in render_signature,

        "no_literal_indent_bug":
            "{indent}"
            not in RENDERER.read_text(
                encoding="utf-8"
            ),
    }

    print()
    print("=" * 64)
    print(" V6 VERIFICATION")
    print("=" * 64)

    failures = []

    for name, result in checks.items():

        status = (
            "PASS"
            if result
            else "FAIL"
        )

        print(
            f"{name}: {status}"
        )

        if not result:
            failures.append(
                name
            )

    if failures:
        raise RuntimeError(
            "V6 verification failed: "
            + ", ".join(
                failures
            )
        )

    print()
    print("=" * 64)
    print(" V6 FIXED INSTALL: PASS")
    print("=" * 64)
    print()
    print(
        "Production files remain patched."
    )
    print(
        "Next step: controlled benchmark render."
    )

except Exception:

    print()
    print("=" * 64)
    print(
        " V6 FIXED INSTALL FAILED"
    )
    print(
        " ROLLING BACK TO CLEAN V5"
    )
    print("=" * 64)
    print()

    traceback.print_exc()

    restore()

    print()
    print(
        "Production files restored."
    )

    try:

        compile_file(
            PIPELINE
        )

        compile_file(
            RENDERER
        )

        print(
            "ROLLBACK COMPILE: PASS"
        )

    except Exception:

        print(
            "ROLLBACK COMPILE: FAIL"
        )

        traceback.print_exc()

    print()
    print(
        "Backup location:"
    )
    print(
        BACKUP_DIR
    )

    sys.exit(1)
