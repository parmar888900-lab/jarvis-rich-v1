from pathlib import Path
import re
import sys

pipeline_path = Path(r"backend/services/pipelines/video_pipeline.py")
renderer_path = Path(r"backend/services/video_renderer/renderer.py")

pipeline = pipeline_path.read_text(encoding="utf-8")
renderer = renderer_path.read_text(encoding="utf-8")

# ============================================================
# V6 PIPELINE IMPORTS
# ============================================================
    # V6 FIXED IMPORT ANCHOR
    if "RICH_V1_VIDEO_BEATS_V6" in pipeline:
        print("V6 pipeline markers already installed.")
    else:
        class_import_anchor = "class VideoPipeline"

        class_import_pos = pipeline.find(
            class_import_anchor
        )

        if class_import_pos < 0:
            raise RuntimeError(
                "Could not locate VideoPipeline class."
            )

        pipeline = (
            pipeline[:class_import_pos]
            + """
# RICH_V1_VIDEO_BEATS_V6
from backend.services.video.source_clip_indexer import SourceClipIndexer

"""
            + pipeline[class_import_pos:]
        )

    # ========================================================
    # ADD VIDEO-BEAT BUILDER TO VideoPipeline
    # ========================================================

    class_anchor = "class VideoPipeline"

    class_pos = pipeline.find(class_anchor)

    if class_pos < 0:
        raise RuntimeError("VideoPipeline class not found.")

    method_anchor = pipeline.find("\n    async def run(", class_pos)

    if method_anchor < 0:
        raise RuntimeError("VideoPipeline.run() anchor not found.")

    helper = r'''
    # ========================================================
    # RICH_V1_VIDEO_BEATS_V6
    # Convert authorized VIDEO assets into exact short source
    # windows that the production renderer can consume.
    #
    # Rights are NOT bypassed here. Only assets already present
    # in the authorized media groups are accepted.
    # ========================================================

    def _v6_build_video_beat_candidates(
        self,
        *,
        media_groups,
        visual_beats,
        content_id,
    ):
        indexer = SourceClipIndexer()

        authorized_videos = []
        seen = set()

        for group in media_groups:
            for asset in group:
                if getattr(asset, "asset_type", "") != "video":
                    continue

                file_path = str(
                    getattr(asset, "file_path", "") or ""
                ).strip()

                if not file_path:
                    continue

                identity = (
                    str(getattr(asset, "asset_id", "") or "")
                    or file_path
                )

                if identity in seen:
                    continue

                seen.add(identity)
                authorized_videos.append(asset)

        if not authorized_videos:
            return {
                "enabled": False,
                "reason": "no_authorized_video_assets",
                "clips": [],
                "assignments": [],
            }

        clips = indexer.index_assets(
            assets=authorized_videos,
            content_id=content_id,
        )

        if not clips:
            return {
                "enabled": False,
                "reason": "video_index_empty",
                "clips": [],
                "assignments": [],
            }

        # ----------------------------------------------------
        # V6 intentionally uses deterministic lexical/domain
        # matching here instead of loading CLIP inside the main
        # render process.
        #
        # Strict CLIP ranking remains available for V6.1, but
        # this integration first proves the production renderer
        # can consume exact moving source segments reliably.
        # ----------------------------------------------------

        def tokens(value):
            import re

            return {
                token
                for token in re.findall(
                    r"[a-z0-9]+",
                    str(value or "").lower(),
                )
                if len(token) >= 3
            }

        assignments = []
        used_clip_ids = set()
        source_usage = {}

        for beat_index, beat in enumerate(visual_beats):
            if isinstance(beat, dict):
                beat_id = str(
                    beat.get("beat_id", f"beat_{beat_index + 1}")
                )

                beat_text = " ".join(
                    str(beat.get(key, "") or "")
                    for key in (
                        "purpose",
                        "search_query",
                        "visual_requirement",
                        "narration",
                    )
                )
            else:
                beat_id = str(
                    getattr(
                        beat,
                        "beat_id",
                        f"beat_{beat_index + 1}",
                    )
                )

                beat_text = " ".join(
                    str(
                        getattr(beat, key, "") or ""
                    )
                    for key in (
                        "purpose",
                        "search_query",
                        "visual_requirement",
                        "narration",
                    )
                )

            beat_tokens = tokens(beat_text)

            ranked = []

            for clip in clips:
                if clip.clip_id in used_clip_ids:
                    continue

                if source_usage.get(clip.source_path, 0) >= 4:
                    continue

                clip_tokens = tokens(
                    " ".join(
                        [
                            clip.source_name,
                            clip.source_path,
                        ]
                    )
                )

                overlap = len(
                    beat_tokens & clip_tokens
                )

                # Slight preference for clips from less-used
                # source videos to force visual diversity.
                reuse_penalty = (
                    source_usage.get(
                        clip.source_path,
                        0,
                    )
                    * 0.35
                )

                score = (
                    float(overlap)
                    - reuse_penalty
                )

                ranked.append(
                    (
                        score,
                        -source_usage.get(
                            clip.source_path,
                            0,
                        ),
                        clip,
                    )
                )

            if not ranked:
                continue

            ranked.sort(
                key=lambda item: (
                    item[0],
                    item[1],
                ),
                reverse=True,
            )

            selected = ranked[0][2]

            used_clip_ids.add(
                selected.clip_id
            )

            source_usage[
                selected.source_path
            ] = (
                source_usage.get(
                    selected.source_path,
                    0,
                )
                + 1
            )

            assignments.append(
                {
                    "beat_id": beat_id,
                    "clip_id": selected.clip_id,
                    "source_path": selected.source_path,
                    "source_name": selected.source_name,
                    "start_time": float(
                        selected.start_time
                    ),
                    "end_time": float(
                        selected.end_time
                    ),
                    "duration": float(
                        selected.duration
                    ),
                    "preview_path": selected.preview_path,
                }
            )

        return {
            "enabled": bool(assignments),
            "reason": (
                "video_beats_ready"
                if assignments
                else "no_video_assignments"
            ),
            "clips": [
                clip.to_dict()
                for clip in clips
            ],
            "assignments": assignments,
        }

'''

    pipeline = (
        pipeline[:method_anchor]
        + "\n"
        + helper
        + pipeline[method_anchor:]
    )

    # ========================================================
    # BUILD V6 VIDEO BEATS IMMEDIATELY BEFORE PACKAGE BUILD
    # ========================================================

    package_anchor = (
        "        package = await self.package_builder.build("
    )

    if package_anchor not in pipeline:
        raise RuntimeError(
            "Production package build anchor not found."
        )

    integration = r'''
        # ====================================================
        # RICH_V1_VIDEO_BEATS_V6
        # Prefer authorized moving footage for semantic beats.
        # The existing image beat sequence remains the safe
        # fallback when no usable authorized video exists.
        # ====================================================

        v6_video_beats = self._v6_build_video_beat_candidates(
            media_groups=media_groups,
            visual_beats=visual_beats,
            content_id=str(
                trend.get(
                    "content_id",
                    "rich_v1",
                )
            ),
        )

'''

    pipeline = pipeline.replace(
        package_anchor,
        integration + package_anchor,
        1,
    )

    # ========================================================
    # PASS V6 ASSIGNMENTS INTO CURRENT PRODUCTION RENDERER
    # ========================================================

    beat_call = "            beat_images=beat_render_assets,"

    if beat_call not in pipeline:
        raise RuntimeError(
            "beat_images renderer-call anchor not found."
        )

    pipeline = pipeline.replace(
        beat_call,
        beat_call + """
            beat_videos=(
                v6_video_beats.get(
                    "assignments",
                    []
                )
            ),""",
        1,
    )

    # Add diagnostic payload to output/package where possible.
    production_marker = (
        '            "production_package": package,'
    )

    if production_marker in pipeline:
        pipeline = pipeline.replace(
            production_marker,
            production_marker + """
            "v6_video_beats": v6_video_beats,""",
            1,
        )

# ============================================================
# V6 RENDERER
# ============================================================

if "RICH_V1_VIDEO_BEATS_V6" not in renderer:

    # VideoFileClip is required.
    if "VideoFileClip" not in renderer:
        moviepy_anchor = "from moviepy import ("

        if moviepy_anchor not in renderer:
            raise RuntimeError(
                "Renderer MoviePy import anchor not found."
            )

        renderer = renderer.replace(
            moviepy_anchor,
            moviepy_anchor + """
    VideoFileClip,""",
            1,
        )

    # Extend render signature.
    signature_anchor = (
        "        beat_images: list[GeneratedImage] | None = None,"
    )

    if signature_anchor not in renderer:
        raise RuntimeError(
            "Renderer beat_images signature anchor not found."
        )

    renderer = renderer.replace(
        signature_anchor,
        signature_anchor + """
        beat_videos: list[dict] | None = None,  # RICH_V1_VIDEO_BEATS_V6""",
        1,
    )

    # Add video tracking beside image_clips.
    clip_anchor = "        image_clips = []"

    if clip_anchor not in renderer:
        raise RuntimeError(
            "Renderer image_clips anchor not found."
        )

    renderer = renderer.replace(
        clip_anchor,
        clip_anchor + """
        video_sources = []  # RICH_V1_VIDEO_BEATS_V6""",
        1,
    )

    # --------------------------------------------------------
    # Replace semantic beat clip construction only.
    #
    # We locate the exact ImageClip creation inside the
    # semantic-beat loop and prepend a moving-footage branch.
    # --------------------------------------------------------

    semantic_marker = "            if use_semantic_beats:"

    semantic_pos = renderer.find(
        semantic_marker
    )

    if semantic_pos < 0:
        raise RuntimeError(
            "Semantic renderer block not found."
        )

    # Find the first ImageClip after the semantic branch.
    imageclip_pos = renderer.find(
        "ImageClip(",
        semantic_pos,
    )

    if imageclip_pos < 0:
        raise RuntimeError(
            "Semantic ImageClip construction not found."
        )

    # Find beginning of the assignment statement containing it.
    line_start = renderer.rfind(
        "\n",
        semantic_pos,
        imageclip_pos,
    ) + 1

    # Walk backwards to find "<name> = (" or "<name> = ImageClip".
    search_region = renderer[
        semantic_pos:imageclip_pos
    ]

    assignment_matches = list(
        re.finditer(
            r"(?m)^(\s+)([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?:\(\s*)?$",
            search_region,
        )
    )

    if not assignment_matches:
        raise RuntimeError(
            "Could not identify semantic ImageClip assignment."
        )

    match = assignment_matches[-1]

    assignment_start = (
        semantic_pos
        + match.start()
    )

    indent = match.group(1)
    variable = match.group(2)

    # Find the logical end of the ImageClip construction by
    # locating the next blank-separated statement. We use the
    # known renderer helper call that follows construction:
    # _prepare_image_clip / resize chain may differ, so inspect
    # until the next line at the same indentation.
    tail = renderer[
        imageclip_pos:
    ]

    # Rather than replacing old code, inject a V6 override
    # immediately AFTER the existing image clip has been built.
    # This keeps V5 behavior as automatic fallback.
    #
    # Find next "image_clips.append" after ImageClip.
    append_pos = renderer.find(
        "image_clips.append",
        imageclip_pos,
    )

    if append_pos < 0:
        raise RuntimeError(
            "Semantic image append anchor not found."
        )

    append_line_start = renderer.rfind(
        "\n",
        imageclip_pos,
        append_pos,
    ) + 1

    v6_override = f'''
{indent}# RICH_V1_VIDEO_BEATS_V6
{indent}# Replace this beat's static image with the exact
{indent}# indexed source-video segment when available.
{indent}if (
{indent}    beat_videos
{indent}    and beat_index < len(beat_videos)
{indent}):
{indent}    video_spec = beat_videos[beat_index]
{indent}    source_path = Path(
{indent}        str(
{indent}            video_spec.get(
{indent}                "source_path",
{indent}                "",
{indent}            )
{indent}        )
{indent}    )
{indent}
{indent}    if source_path.exists():
{indent}        source_video = VideoFileClip(
{indent}            str(source_path)
{indent}        )
{indent}
{indent}        video_sources.append(
{indent}            source_video
{indent}        )
{indent}
{indent}        start_time = max(
{indent}            0.0,
{indent}            float(
{indent}                video_spec.get(
{indent}                    "start_time",
{indent}                    0.0,
{indent}                )
{indent}            ),
{indent}        )
{indent}
{indent}        end_time = min(
{indent}            float(source_video.duration),
{indent}            float(
{indent}                video_spec.get(
{indent}                    "end_time",
{indent}                    start_time + cut_duration,
{indent}                )
{indent}            ),
{indent}        )
{indent}
{indent}        if end_time > start_time:
{indent}            moving = (
{indent}                source_video
{indent}                .subclipped(
{indent}                    start_time,
{indent}                    end_time,
{indent}                )
{indent}                .without_audio()
{indent}            )
{indent}
{indent}            # Loop a short exact source window only
{indent}            # when narration timing requires slightly
{indent}            # more duration than the indexed segment.
{indent}            if moving.duration < cut_duration:
{indent}                repeats = max(
{indent}                    1,
{indent}                    int(
{indent}                        cut_duration
{indent}                        / max(
{indent}                            0.05,
{indent}                            moving.duration,
{indent}                        )
{indent}                    )
{indent}                    + 1,
{indent}                )
{indent}
{indent}                moving = concatenate_videoclips(
{indent}                    [moving] * repeats,
{indent}                    method="compose",
{indent}                )
{indent}
{indent}            moving = moving.subclipped(
{indent}                0,
{indent}                min(
{indent}                    cut_duration,
{indent}                    moving.duration,
{indent}                ),
{indent}            )
{indent}
{indent}            moving = self._fit_visual(
{indent}                moving,
{indent}                cut_duration,
{indent}            )
{indent}
{indent}            {variable} = moving

'''

    renderer = (
        renderer[:append_line_start]
        + v6_override
        + renderer[append_line_start:]
    )

    # Ensure concatenate_videoclips exists.
    if "concatenate_videoclips" not in renderer:
        raise RuntimeError(
            "Renderer lacks concatenate_videoclips import."
        )

    # Close opened source videos in finally.
    finally_anchor = (
        "            for clip in image_clips:"
    )

    if finally_anchor in renderer:
        renderer = renderer.replace(
            finally_anchor,
            """            # RICH_V1_VIDEO_BEATS_V6
            for source_video in video_sources:
                try:
                    source_video.close()
                except Exception:
                    pass

""" + finally_anchor,
            1,
        )

pipeline_path.write_text(
    pipeline,
    encoding="utf-8",
)

renderer_path.write_text(
    renderer,
    encoding="utf-8",
)

print("V6 patch installed.")

