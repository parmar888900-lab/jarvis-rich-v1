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
    / f"v6_3_phase2_{STAMP}"
    / "backup"
)
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

BACKUP = BACKUP_DIR / "video_pipeline.py"
shutil.copy2(PIPE, BACKUP)

print("=" * 70)
print(" RICH V1 - V6.3 PHASE 2 MOVIE MEDIA BRIDGE")
print("=" * 70)
print("BACKUP:", BACKUP)

source = PIPE.read_text(encoding="utf-8")

marker = "        # RICH_V1_VIDEO_ACQUISITION_V6_2"

if marker not in source:
    raise RuntimeError(
        "V6.2 acquisition marker not found."
    )

if "RICH_V1_MOVIE_MEDIA_BRIDGE_V6_3" not in source:

    bridge = r'''
        # ====================================================
        # RICH_V1_MOVIE_MEDIA_BRIDGE_V6_3
        # ====================================================
        #
        # Famous-movie commentary receives a dedicated
        # beat-preserving media resolution pass.
        #
        # This does NOT weaken provenance/licensing policy.
        # MovieMediaResolver remains the authorization gate.
        #
        # Non-movie formats continue through the existing
        # V6.2 acquisition path unchanged.

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

            resolved_count = 0
            unresolved_count = 0

            for beat_index, resolved in enumerate(
                resolved_movie_beats
            ):

                asset = resolved.asset

                evidence_row = resolved.to_dict()
                evidence_row["beat_index"] = (
                    beat_index + 1
                )

                v63_movie_media_evidence[
                    "beats"
                ].append(evidence_row)

                if asset is None:
                    unresolved_count += 1
                    continue

                resolved_count += 1

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
            # Preserve exact beat -> asset mapping.
            #
            # Existing media_groups are retained because they
            # contain the proven fallback path. The dedicated
            # movie asset is inserted at the front of its
            # corresponding group so downstream V6.1 sees it.
            # ------------------------------------------------

            for beat_index, asset in (
                movie_video_assets
                + movie_image_assets
            ):

                if not media_groups:
                    break

                target_group = (
                    beat_index
                    % len(media_groups)
                )

                existing = {
                    self._master_asset_identity(item)
                    for item in media_groups[target_group]
                }

                identity = (
                    self._master_asset_identity(
                        asset
                    )
                )

                if (
                    identity
                    and identity not in existing
                ):
                    media_groups[
                        target_group
                    ].insert(
                        0,
                        asset,
                    )

            # ------------------------------------------------
            # Movie IMAGE assets replace the generic semantic
            # image for that exact beat. This keeps images as
            # deterministic fallback if a video cannot render.
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

            v63_movie_media_evidence.update(
                {
                    "status": (
                        "resolved"
                        if resolved_count
                        else "no_authorized_movie_media"
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
        marker,
        bridge + "\n" + marker,
        1,
    )

# ------------------------------------------------------------
# Disable generic V6.2 acquisition ONLY for movie commentary.
#
# Movie commentary has already gone through its stricter
# MovieMediaResolver. Other formats behave exactly as before.
# ------------------------------------------------------------

old = '''        v62_source_result = (
            await self._v62_acquire_source_footage(
                format_name=v62_format_name,
                topic=str(topic),
                content_id=str(content_id),
            )
        )
'''

new = '''        if is_movie_commentary:
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

if (
    "skipped_for_movie_commentary"
    not in source
):
    if old not in source:
        raise RuntimeError(
            "Exact V6.2 acquisition call not found."
        )

    source = source.replace(
        old,
        new,
        1,
    )

# ------------------------------------------------------------
# Add V6.3 evidence to the final result if the existing result
# already exposes V6.1/V6.2 evidence.
# ------------------------------------------------------------

needle = (
    '"v6_video_acquisition": '
    "v62_source_result,"
)

replacement = (
    '"v6_movie_media": '
    "v63_movie_media_evidence,\n"
    '            "v6_video_acquisition": '
    "v62_source_result,"
)

if '"v6_movie_media"' not in source:
    if needle not in source:
        raise RuntimeError(
            "Final V6.2 evidence anchor not found."
        )

    source = source.replace(
        needle,
        replacement,
        1,
    )

PIPE.write_text(
    source,
    encoding="utf-8",
)

# ------------------------------------------------------------
# Compile + structural verification
# ------------------------------------------------------------

checks = {
    "phase1_preserved":
        "RICH_V1_MOVIE_MEDIA_V6_3"
        in source,

    "phase2_marker":
        "RICH_V1_MOVIE_MEDIA_BRIDGE_V6_3"
        in source,

    "resolver_called":
        "self.movie_media_resolver.resolve("
        in source,

    "exact_beats_passed":
        "beats=visual_beats"
        in source,

    "movie_title_passed":
        "movie_title=movie_title"
        in source,

    "content_id_passed":
        "content_id=str(content_id)"
        in source,

    "beat_mapping_preserved":
        "movie_video_assets.append("
        in source,

    "movie_image_fallback":
        "beat_render_assets[\n"
        "                        beat_index\n"
        "                    ] = asset"
        in source,

    "generic_movie_acquisition_disabled":
        "skipped_for_movie_commentary"
        in source,

    "v62_nonmovie_preserved":
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

    "evidence_added":
        '"v6_movie_media"'
        in source,
}

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

print()
print("V6.3 PHASE 2 VERIFICATION")

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
    print("V6.3 PHASE 2: FAIL")
    print(
        "Automatic rollback completed."
    )
    sys.exit(1)

print()
print("V6.3 PHASE 2: PASS")
print(
    "MovieMediaResolver is now connected "
    "to movie production."
)
print(
    "Exact movie beat mapping is preserved."
)
print(
    "Movie images remain per-beat fallback."
)
print(
    "Generic V6.2 acquisition is skipped "
    "only for famous_movie_commentary."
)
print(
    "V6.1 matching + renderer remain intact."
)
