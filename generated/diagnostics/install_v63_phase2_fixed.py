from pathlib import Path
from datetime import datetime
import shutil
import py_compile
import sys

ROOT = Path(r"C:\Users\hp\jarvis.ai")
PIPE = ROOT / "backend/services/pipelines/video_pipeline.py"

STAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
BACKUP_DIR = (
    ROOT / "generated/diagnostics"
    / f"v6_3_phase2_fixed_{STAMP}"
    / "backup"
)
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

BACKUP = BACKUP_DIR / "video_pipeline.py"
shutil.copy2(PIPE, BACKUP)

print("=" * 72)
print(" RICH V1 - V6.3 PHASE 2 FIXED MOVIE MEDIA BRIDGE")
print("=" * 72)
print("BACKUP:", BACKUP)

source = PIPE.read_text(encoding="utf-8")

# ------------------------------------------------------------
# Safety: previous failed installer should have rolled back.
# ------------------------------------------------------------

if "RICH_V1_MOVIE_MEDIA_BRIDGE_V6_3" in source:
    raise RuntimeError(
        "Phase 2 marker already exists. "
        "Refusing to double-patch."
    )

if "RICH_V1_MOVIE_MEDIA_V6_3" not in source:
    raise RuntimeError(
        "V6.3 Phase 1 is not present."
    )

# ------------------------------------------------------------
# 1. Find the REAL executable V6.2 production block.
#
# Do NOT anchor on the comment marker because that marker can
# occur elsewhere in the file.
# ------------------------------------------------------------

production_anchor = (
    "        v62_format_name = str(\n"
)

count = source.count(production_anchor)

print(
    "production_v62_anchor_count:",
    count,
)

if count != 1:
    raise RuntimeError(
        "Expected exactly one executable "
        f"v62_format_name block, found {count}."
    )

bridge = r'''
        # ====================================================
        # RICH_V1_MOVIE_MEDIA_BRIDGE_V6_3
        # ====================================================
        #
        # Famous-movie commentary uses the dedicated,
        # rights-aware MovieMediaResolver.
        #
        # Exact beat identity is retained in evidence.
        # Resolved assets are inserted into the existing media
        # structures so the proven V6.1 matcher/renderer can
        # continue downstream.
        #
        # Non-movie formats remain unchanged.

        v63_movie_media_evidence = {
            "status": "not_applicable",
            "movie_title": "",
            "resolved_beats": 0,
            "video_assets": 0,
            "image_assets": 0,
            "unresolved_beats": 0,
            "beats": [],
        }

        if is_movie_commentary:

            resolved_movie_beats = (
                await self.movie_media_resolver.resolve(
                    beats=visual_beats,
                    content_id=str(content_id),
                    movie_title=movie_title,
                )
            )

            if (
                len(resolved_movie_beats)
                != len(visual_beats)
            ):
                raise RuntimeError(
                    "V6.3 movie resolver returned "
                    "beat coverage mismatch."
                )

            movie_video_assets = []
            movie_image_assets = []

            for beat_index, resolved in enumerate(
                resolved_movie_beats
            ):

                asset = resolved.asset

                row = resolved.to_dict()
                row["beat_index"] = (
                    beat_index + 1
                )

                v63_movie_media_evidence[
                    "beats"
                ].append(row)

                if asset is None:
                    continue

                asset_type = str(
                    getattr(
                        asset,
                        "asset_type",
                        "",
                    )
                ).strip().lower()

                if asset_type == "video":
                    movie_video_assets.append(
                        (
                            beat_index,
                            asset,
                        )
                    )

                elif asset_type == "image":
                    movie_image_assets.append(
                        (
                            beat_index,
                            asset,
                        )
                    )

            # ------------------------------------------------
            # Inject authorized movie assets into the existing
            # scene groups without deleting proven fallbacks.
            #
            # Scene groups and visual beats can have different
            # counts, so mapping is deterministic modulo scene
            # count while the exact beat mapping remains in
            # v63_movie_media_evidence.
            # ------------------------------------------------

            if media_groups:

                for beat_index, asset in (
                    movie_video_assets
                    + movie_image_assets
                ):

                    target_group = (
                        beat_index
                        % len(media_groups)
                    )

                    identity = (
                        self._master_asset_identity(
                            asset
                        )
                    )

                    existing = {
                        self._master_asset_identity(
                            item
                        )
                        for item
                        in media_groups[
                            target_group
                        ]
                    }

                    if (
                        identity
                        and identity
                        not in existing
                    ):
                        media_groups[
                            target_group
                        ].insert(
                            0,
                            asset,
                        )

            # ------------------------------------------------
            # For exact beat-level image fallback, replace the
            # generic beat image only where MovieMediaResolver
            # returned an authorized image for that same beat.
            # ------------------------------------------------

            for beat_index, asset in (
                movie_image_assets
            ):

                if (
                    0
                    <= beat_index
                    < len(beat_render_assets)
                ):
                    beat_render_assets[
                        beat_index
                    ] = asset

            resolved_count = (
                len(movie_video_assets)
                + len(movie_image_assets)
            )

            unresolved_count = (
                len(visual_beats)
                - resolved_count
            )

            v63_movie_media_evidence.update(
                {
                    "status": (
                        "resolved"
                        if resolved_count > 0
                        else
                        "no_authorized_movie_media"
                    ),
                    "movie_title": movie_title,
                    "resolved_beats": (
                        resolved_count
                    ),
                    "video_assets": len(
                        movie_video_assets
                    ),
                    "image_assets": len(
                        movie_image_assets
                    ),
                    "unresolved_beats": (
                        unresolved_count
                    ),
                }
            )

'''

source = source.replace(
    production_anchor,
    bridge + "\n" + production_anchor,
    1,
)

# ------------------------------------------------------------
# 2. Skip generic V6.2 source acquisition ONLY for dedicated
#    movie commentary.
# ------------------------------------------------------------

old_call = '''        v62_source_result = (
            await self._v62_acquire_source_footage(
                format_name=v62_format_name,
                topic=str(topic),
                content_id=str(content_id),
            )
        )
'''

new_call = '''        if is_movie_commentary:
            v62_source_result = {
                "status": "skipped_for_movie_commentary",
                "reason": "dedicated_movie_media_resolver",
                "assets": [],
                "asset_count": 0,
            }
        else:
            v62_source_result = (
                await self._v62_acquire_source_footage(
                    format_name=v62_format_name,
                    topic=str(topic),
                    content_id=str(content_id),
                )
            )
'''

call_count = source.count(old_call)

print(
    "v62_acquisition_call_count:",
    call_count,
)

if call_count != 1:
    raise RuntimeError(
        "Expected exactly one executable V6.2 "
        f"acquisition call, found {call_count}."
    )

source = source.replace(
    old_call,
    new_call,
    1,
)

# ------------------------------------------------------------
# 3. Add V6.3 evidence beside existing V6.2 evidence.
# ------------------------------------------------------------

evidence_anchor = (
    '            "v6_video_acquisition": '
    'v62_source_result,\n'
)

evidence_count = source.count(
    evidence_anchor
)

print(
    "v62_evidence_anchor_count:",
    evidence_count,
)

if evidence_count != 1:
    raise RuntimeError(
        "Expected exactly one V6.2 result evidence "
        f"anchor, found {evidence_count}."
    )

source = source.replace(
    evidence_anchor,
    (
        '            "v6_movie_media": '
        'v63_movie_media_evidence,\n'
        + evidence_anchor
    ),
    1,
)

PIPE.write_text(
    source,
    encoding="utf-8",
)

# ------------------------------------------------------------
# 4. Compile FIRST.
# ------------------------------------------------------------

try:
    py_compile.compile(
        str(PIPE),
        doraise=True,
    )
    compile_ok = True

except Exception as exc:
    compile_ok = False
    print(
        "COMPILE ERROR:",
        repr(exc),
    )

# ------------------------------------------------------------
# 5. Structural verification.
# ------------------------------------------------------------

checks = {
    "phase1_preserved":
        "RICH_V1_MOVIE_MEDIA_V6_3"
        in source,

    "phase2_marker":
        "RICH_V1_MOVIE_MEDIA_BRIDGE_V6_3"
        in source,

    "resolver_called":
        "await self.movie_media_resolver.resolve("
        in source,

    "exact_movie_beats":
        "beats=visual_beats"
        in source,

    "content_id_preserved":
        "content_id=str(content_id)"
        in source,

    "movie_title_preserved":
        "movie_title=movie_title"
        in source,

    "movie_video_assets":
        "movie_video_assets.append("
        in source,

    "movie_image_assets":
        "movie_image_assets.append("
        in source,

    "image_fallback_preserved":
        "beat_render_assets[\n"
        "                        beat_index\n"
        "                    ] = asset"
        in source,

    "movie_generic_v62_skipped":
        "skipped_for_movie_commentary"
        in source,

    "nonmovie_v62_preserved":
        "await self._v62_acquire_source_footage("
        in source,

    "v61_preserved":
        "_v61_build_video_matches"
        in source,

    "renderer_video_preserved":
        "beat_videos=v61_video_matches"
        in source,

    "block5_preserved":
        "BLOCK5_VISUAL_QA_BEGIN"
        in source,

    "movie_evidence":
        '"v6_movie_media"'
        in source,
}

print()
print("V6.3 PHASE 2 FIXED VERIFICATION")

for name, ok in checks.items():
    print(
        f"{name}: "
        f"{'PASS' if ok else 'FAIL'}"
    )

print(
    "PATCHED COMPILE:",
    "PASS" if compile_ok else "FAIL",
)

all_ok = (
    compile_ok
    and all(checks.values())
)

if not all_ok:

    shutil.copy2(
        BACKUP,
        PIPE,
    )

    print()
    print("V6.3 PHASE 2 FIXED: FAIL")
    print(
        "Automatic rollback completed."
    )
    sys.exit(1)

print()
print("V6.3 PHASE 2 FIXED: PASS")
print(
    "MovieMediaResolver is connected inside "
    "the async production path."
)
print(
    "Dedicated movie media now precedes V6.1 matching."
)
print(
    "Generic V6.2 acquisition is skipped only "
    "for famous_movie_commentary."
)
print(
    "Non-movie production paths remain preserved."
)
