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
    / f"v6_1_{STAMP}"
    / "backup"
)

BACKUP_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

PIPELINE_BACKUP = BACKUP_DIR / "video_pipeline.py"
RENDERER_BACKUP = BACKUP_DIR / "renderer.py"

MARKER = "RICH_V1_REAL_VIDEO_V6_1"


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
            f"{label}: expected exactly 1 occurrence; "
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


print("=" * 68)
print(" RICH V1 — V6.1 REAL VIDEO INTEGRATION")
print("=" * 68)
print()


# ============================================================
# 0. VERIFY CLEAN BASELINE
# ============================================================

compile_file(PIPELINE)
compile_file(RENDERER)

print("BASELINE COMPILE: PASS")

pipeline = PIPELINE.read_text(
    encoding="utf-8"
)

renderer = RENDERER.read_text(
    encoding="utf-8"
)

# Previous failed installers should have rolled back completely.
for old_marker in (
    "RICH_V1_REAL_VIDEO_V6_FIXED",
    "RICH_V1_REAL_VIDEO_V6\n",
):
    if old_marker in pipeline or old_marker in renderer:
        raise RuntimeError(
            "A previous V6 patch marker still exists. "
            "Refusing to patch a non-clean baseline."
        )

if MARKER in pipeline or MARKER in renderer:
    raise RuntimeError(
        "V6.1 already appears installed."
    )


# ============================================================
# 1. BACKUP EXACTLY TWO PRODUCTION FILES
# ============================================================

shutil.copy2(
    PIPELINE,
    PIPELINE_BACKUP,
)

shutil.copy2(
    RENDERER,
    RENDERER_BACKUP,
)

print(f"BACKUP: {BACKUP_DIR}")


try:

    # ========================================================
    # PIPELINE PATCH
    # ========================================================

    # --------------------------------------------------------
    # 2. IMPORT EXISTING REAL-VIDEO STACK
    # --------------------------------------------------------

    class_anchor = "class VideoPipeline:"

    require_once(
        pipeline,
        class_anchor,
        "VideoPipeline class",
    )

    imports = '''# RICH_V1_REAL_VIDEO_V6_1
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
        class_anchor,
        imports + class_anchor,
        "pipeline V6.1 imports",
    )


    # --------------------------------------------------------
    # 3. ADD FAIL-SOFT VIDEO MATCHING HELPERS
    # --------------------------------------------------------

    run_anchor = "    async def run(\n"

    require_once(
        pipeline,
        run_anchor,
        "VideoPipeline.run",
    )

    helper_code = '''
    # ========================================================
    # RICH_V1_REAL_VIDEO_V6_1
    # ========================================================

    @staticmethod
    def _v61_make_source_beat(
        beat,
        beat_index: int,
    ):
        """
        Convert the current VisualBeat into the existing
        SourceVisualBeat contract used by StrictClipMatcher.

        Reflection is intentional here so optional fields can
        evolve without breaking the V5 image fallback.
        """

        import dataclasses

        try:
            source_fields = {
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
                "",
            )
            or f"beat_{beat_index + 1}"
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

        primary_query = str(
            getattr(
                beat,
                "search_query",
                "",
            )
            or visual_goal
        ).strip()

        values = {}

        if "beat_id" in source_fields:
            values["beat_id"] = beat_id

        if "visual_goal" in source_fields:
            values["visual_goal"] = visual_goal

        if "search_queries" in source_fields:

            queries = []

            raw_queries = getattr(
                beat,
                "search_queries",
                None,
            )

            if raw_queries:
                queries.extend(
                    str(item).strip()
                    for item in raw_queries
                    if str(item).strip()
                )

            if (
                primary_query
                and primary_query not in queries
            ):
                queries.insert(
                    0,
                    primary_query,
                )

            if not queries and visual_goal:
                queries.append(
                    visual_goal
                )

            values["search_queries"] = (
                queries[:4]
            )

        if "negative_visuals" in source_fields:

            negative = getattr(
                beat,
                "negative_visuals",
                None,
            )

            if negative:
                negative = [
                    str(item).strip()
                    for item in negative
                    if str(item).strip()
                ]
            else:
                negative = [
                    "generic stock footage",
                    "unrelated person talking to camera",
                    "irrelevant lifestyle footage",
                    "unrelated object footage",
                ]

            values[
                "negative_visuals"
            ] = negative

        # Copy compatible fields directly when available.
        for field_name in source_fields:

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


    def _v61_build_video_matches(
        self,
        *,
        media_groups,
        visual_beats,
        content_id: str,
    ) -> dict:
        """
        Existing authorized MediaAsset videos
            -> SourceClipIndexer
            -> StrictClipMatcher
            -> exact source timestamps.

        Failure at any point returns to V5 image rendering.
        """

        videos = []
        seen = set()

        # ----------------------------------------------------
        # Only use assets that already passed the production
        # acquisition/authorization layer.
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

                source_path = str(
                    getattr(
                        asset,
                        "file_path",
                        "",
                    )
                    or ""
                ).strip()

                if not source_path:
                    continue

                if not Path(
                    source_path
                ).exists():
                    continue

                identity = str(
                    getattr(
                        asset,
                        "asset_id",
                        "",
                    )
                    or source_path
                )

                if identity in seen:
                    continue

                seen.add(identity)
                videos.append(asset)

        if not videos:

            return {
                "status":
                    "fallback_images",

                "reason":
                    "no_authorized_video_assets",

                "authorized_video_assets":
                    0,

                "indexed_clips":
                    0,

                "matched_beats":
                    0,

                "matches":
                    [],
            }

        # ----------------------------------------------------
        # Index exact 1–3 second source moments.
        # ----------------------------------------------------

        try:

            indexer = SourceClipIndexer()

            clips = indexer.index_assets(
                assets=videos,
                content_id=content_id,
            )

        except Exception as exc:

            return {
                "status":
                    "fallback_images",

                "reason":
                    (
                        "source_clip_indexer:"
                        + type(exc).__name__
                    ),

                "authorized_video_assets":
                    len(videos),

                "indexed_clips":
                    0,

                "matched_beats":
                    0,

                "matches":
                    [],
            }

        if not clips:

            return {
                "status":
                    "fallback_images",

                "reason":
                    "no_indexed_video_clips",

                "authorized_video_assets":
                    len(videos),

                "indexed_clips":
                    0,

                "matched_beats":
                    0,

                "matches":
                    [],
            }

        source_beats = []
        index_by_beat_id = {}

        for zero_index, beat in enumerate(
            visual_beats
        ):

            source_beat = (
                self._v61_make_source_beat(
                    beat,
                    zero_index,
                )
            )

            if source_beat is None:
                continue

            source_beats.append(
                source_beat
            )

            # Renderer beat_index starts at 1.
            index_by_beat_id[
                str(source_beat.beat_id)
            ] = zero_index + 1

        if not source_beats:

            return {
                "status":
                    "fallback_images",

                "reason":
                    "source_beat_conversion_failed",

                "authorized_video_assets":
                    len(videos),

                "indexed_clips":
                    len(clips),

                "matched_beats":
                    0,

                "matches":
                    [],
            }

        # ----------------------------------------------------
        # Existing strict positive/negative CLIP matcher.
        # ----------------------------------------------------

        try:

            matcher = StrictClipMatcher()

            matches = matcher.match_many(
                beats=source_beats,
                clips=clips,

                # Stronger diversity than class default.
                max_reuse_per_source=3,
            )

        except Exception as exc:

            return {
                "status":
                    "fallback_images",

                "reason":
                    (
                        "strict_clip_matcher:"
                        + type(exc).__name__
                    ),

                "authorized_video_assets":
                    len(videos),

                "indexed_clips":
                    len(clips),

                "matched_beats":
                    0,

                "matches":
                    [],
            }

        renderer_matches = []

        for match in matches:

            beat_index = (
                index_by_beat_id.get(
                    str(match.beat_id)
                )
            )

            if beat_index is None:
                continue

            renderer_matches.append(
                {
                    "beat_index":
                        int(beat_index),

                    "beat_id":
                        str(match.beat_id),

                    "visual_goal":
                        str(
                            match.visual_goal
                        ),

                    "clip_id":
                        str(match.clip_id),

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
                    if renderer_matches
                    else "fallback_images"
                ),

            "reason":
                (
                    "strict_semantic_matches"
                    if renderer_matches
                    else "no_strict_matches"
                ),

            "authorized_video_assets":
                len(videos),

            "indexed_clips":
                len(clips),

            "matched_beats":
                len(renderer_matches),

            "matches":
                renderer_matches,
        }


'''

    pipeline = replace_once(
        pipeline,
        run_anchor,
        helper_code + run_anchor,
        "V6.1 helper insertion",
    )


    # --------------------------------------------------------
    # 4. RUN MATCHER BEFORE PACKAGE BUILD
    # --------------------------------------------------------

    package_anchor = (
        "        package = await "
        "self.package_builder.build(\n"
    )

    require_once(
        pipeline,
        package_anchor,
        "package builder",
    )

    match_call = '''
        # ====================================================
        # RICH_V1_REAL_VIDEO_V6_1
        # ====================================================

        v61_video_result = (
            self._v61_build_video_matches(
                media_groups=media_groups,
                visual_beats=visual_beats,
                content_id=str(
                    content_id
                ),
            )
        )

        v61_video_matches = list(
            v61_video_result.get(
                "matches",
                [],
            )
        )

'''

    pipeline = replace_once(
        pipeline,
        package_anchor,
        match_call + package_anchor,
        "V6.1 matching call",
    )


    # --------------------------------------------------------
    # 5. PASS MATCHES INTO EXISTING PRODUCTION RENDERER
    # --------------------------------------------------------

    renderer_call_anchor = (
        "            beat_images="
        "beat_render_assets,\n"
    )

    require_once(
        pipeline,
        renderer_call_anchor,
        "renderer beat_images call",
    )

    pipeline = replace_once(
        pipeline,
        renderer_call_anchor,
        renderer_call_anchor
        + (
            "            beat_videos="
            "v61_video_matches,\n"
        ),
        "renderer beat_videos call",
    )


    # --------------------------------------------------------
    # 6. RETURN V6.1 EVIDENCE
    # --------------------------------------------------------

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
            'v61_video_result,\n'
        ),
        "V6.1 evidence",
    )


    # ========================================================
    # RENDERER PATCH
    # ========================================================

    # --------------------------------------------------------
    # 7. IMPORT VideoFileClip
    # --------------------------------------------------------

    import_anchor = (
        "    ImageClip,\n"
    )

    require_once(
        renderer,
        import_anchor,
        "ImageClip import",
    )

    renderer = replace_once(
        renderer,
        import_anchor,
        import_anchor
        + "    VideoFileClip,\n",
        "VideoFileClip import",
    )


    # --------------------------------------------------------
    # 8. ADD beat_videos ARGUMENT
    # --------------------------------------------------------

    signature_anchor = (
        "        beat_images: "
        "list[GeneratedImage] | None = None,\n"
    )

    require_once(
        renderer,
        signature_anchor,
        "renderer beat_images signature",
    )

    renderer = replace_once(
        renderer,
        signature_anchor,
        signature_anchor
        + (
            "        beat_videos: "
            "list[dict] | None = None,\n"
        ),
        "renderer beat_videos signature",
    )


    # --------------------------------------------------------
    # 9. TRACK VIDEO SOURCE HANDLES
    #
    # Exact current source:
    #     image_clips = []
    #     subtitle_clips = []
    # --------------------------------------------------------

    init_anchor = '''        image_clips = []
        subtitle_clips = []
'''

    require_once(
        renderer,
        init_anchor,
        "renderer clip initialization",
    )

    init_replacement = '''        image_clips = []
        subtitle_clips = []

        # RICH_V1_REAL_VIDEO_V6_1
        video_source_clips = []

        beat_video_lookup = {
            int(
                item.get(
                    "beat_index",
                    -1,
                )
            ): item
            for item in (beat_videos or [])
            if isinstance(
                item,
                dict,
            )
        }
'''

    renderer = replace_once(
        renderer,
        init_anchor,
        init_replacement,
        "V6.1 renderer initialization",
    )


    # --------------------------------------------------------
    # 10. EXACT SEMANTIC BLOCK REPLACEMENT
    #
    # This is the exact current production source confirmed
    # by v6_renderer_exact_context.txt.
    #
    # NO regex.
    # NO loop inference.
    # NO indentation inference.
    # --------------------------------------------------------

    old_semantic_block = '''                    clip = self._cover_image_clip(
                        image_path=image_path,
                        duration=cut_duration,
                        zoom=zoom,
                    )

                    image_clips.append(
                        clip
                    )
'''

    require_once(
        renderer,
        old_semantic_block,
        "exact semantic image block",
    )

    new_semantic_block = '''                    # RICH_V1_REAL_VIDEO_V6_1
                    #
                    # Default remains the existing authorized
                    # image. A strict semantic video match can
                    # replace it for this beat.
                    clip = None

                    video_spec = beat_video_lookup.get(
                        beat_index
                    )

                    if video_spec is not None:

                        source_path = Path(
                            str(
                                video_spec.get(
                                    "source_path",
                                    "",
                                )
                            )
                        )

                        if source_path.exists():

                            source_video = None

                            try:

                                source_video = (
                                    VideoFileClip(
                                        str(
                                            source_path
                                        )
                                    )
                                )

                                video_source_clips.append(
                                    source_video
                                )

                                start_time = max(
                                    0.0,
                                    float(
                                        video_spec.get(
                                            "start_time",
                                            0.0,
                                        )
                                    ),
                                )

                                end_time = min(
                                    float(
                                        source_video.duration
                                    ),
                                    float(
                                        video_spec.get(
                                            "end_time",
                                            start_time
                                            + cut_duration,
                                        )
                                    ),
                                )

                                if (
                                    end_time
                                    > start_time
                                    + 0.05
                                ):

                                    moving_clip = (
                                        source_video
                                        .subclipped(
                                            start_time,
                                            end_time,
                                        )
                                        .without_audio()
                                    )

                                    available_duration = (
                                        float(
                                            moving_clip.duration
                                        )
                                    )

                                    if (
                                        available_duration
                                        >= cut_duration
                                    ):

                                        moving_clip = (
                                            moving_clip
                                            .subclipped(
                                                0.0,
                                                cut_duration,
                                            )
                                        )

                                        clip = (
                                            self._fit_visual(
                                                moving_clip,
                                                cut_duration,
                                            )
                                        )

                                    else:

                                        # Do not stretch/freeze a
                                        # short clip just to force
                                        # a match. Fall back to
                                        # the authorized image.
                                        clip = None

                            except Exception:

                                clip = None

                    if clip is None:

                        clip = self._cover_image_clip(
                            image_path=image_path,
                            duration=cut_duration,
                            zoom=zoom,
                        )

                    image_clips.append(
                        clip
                    )
'''

    renderer = replace_once(
        renderer,
        old_semantic_block,
        new_semantic_block,
        "V6.1 exact semantic replacement",
    )


    # --------------------------------------------------------
    # 11. CLOSE VideoFileClip SOURCE HANDLES
    #
    # Exact existing finally section has:
    #     for clip in image_clips:
    #         clip.close()
    # --------------------------------------------------------

    cleanup_anchor = '''            for clip in image_clips:
                clip.close()

            audio.close()
'''

    require_once(
        renderer,
        cleanup_anchor,
        "renderer cleanup block",
    )

    cleanup_replacement = '''            for clip in image_clips:
                clip.close()

            # RICH_V1_REAL_VIDEO_V6_1
            for source_video in video_source_clips:
                try:
                    source_video.close()
                except Exception:
                    pass

            audio.close()
'''

    renderer = replace_once(
        renderer,
        cleanup_anchor,
        cleanup_replacement,
        "V6.1 video cleanup",
    )


    # ========================================================
    # 12. WRITE PATCHED FILES
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
    # 14. IMPORT SMOKE TEST
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

        "pipeline_v61_helper":
            hasattr(
                VideoPipeline,
                "_v61_build_video_matches",
            ),

        "source_clip_indexer":
            SourceClipIndexer
            is not None,

        "strict_clip_matcher":
            StrictClipMatcher
            is not None,

        "renderer_accepts_beat_videos":
            "beat_videos"
            in render_signature,

        "renderer_keeps_beat_images":
            "beat_images"
            in render_signature,

        "renderer_video_file_clip":
            "VideoFileClip"
            in RENDERER.read_text(
                encoding="utf-8"
            ),

        "exact_image_fallback_preserved":
            (
                "if clip is None:"
                in RENDERER.read_text(
                    encoding="utf-8"
                )
                and
                "self._cover_image_clip("
                in RENDERER.read_text(
                    encoding="utf-8"
                )
            ),
    }

    print()
    print("=" * 68)
    print(" V6.1 VERIFICATION")
    print("=" * 68)

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
            "V6.1 verification failed: "
            + ", ".join(failed)
        )


    # ========================================================
    # 15. CONFIRM EXACT SEMANTIC LOOP REMAINS PRESENT
    # ========================================================

    final_renderer = (
        RENDERER.read_text(
            encoding="utf-8"
        )
    )

    required_runtime_fragments = [
        "for beat_index, (",
        "cut_duration,",
        ") in enumerate(",
        "beat_video_lookup.get(",
        "VideoFileClip(",
        ".subclipped(",
        ".without_audio()",
        "if clip is None:",
        "image_clips.append(",
    ]

    for fragment in required_runtime_fragments:

        if fragment not in final_renderer:

            raise RuntimeError(
                "Runtime fragment missing: "
                + fragment
            )


    print()
    print("=" * 68)
    print(" V6.1 INSTALL: PASS")
    print("=" * 68)
    print()
    print(
        "Real-video production path is now connected."
    )
    print(
        "V5 authorized images remain per-beat fallback."
    )
    print()
    print(
        "NEXT: run controlled benchmark."
    )


except Exception:

    print()
    print("=" * 68)
    print(" V6.1 INSTALL FAILED")
    print(" RESTORING CLEAN V5")
    print("=" * 68)
    print()

    traceback.print_exc()

    restore()

    print()
    print(
        "Original production files restored."
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
        "Backup:"
    )
    print(
        BACKUP_DIR
    )

    sys.exit(1)
