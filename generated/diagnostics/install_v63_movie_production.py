from pathlib import Path
from datetime import datetime
import py_compile
import shutil
import sys

ROOT = Path(r"C:\Users\hp\jarvis.ai")
PIPE = ROOT / "backend/services/pipelines/video_pipeline.py"
STAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
BACKUP_DIR = ROOT / "generated/diagnostics" / f"v6_3_{STAMP}" / "backup"
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

BACKUP = BACKUP_DIR / "video_pipeline.py"
shutil.copy2(PIPE, BACKUP)

print("=" * 68)
print(" RICH V1 - V6.3 MOVIE-SPECIFIC PRODUCTION PATH")
print("=" * 68)
print("BACKUP:", BACKUP)

source = PIPE.read_text(encoding="utf-8")
original = source

# ------------------------------------------------------------
# 1. Imports
# ------------------------------------------------------------

anchor = (
    "from backend.services.storyboard.generator import StoryboardGenerator\n"
)

addition = (
    "from backend.services.storyboard.generator import StoryboardGenerator\n"
    "# RICH_V1_MOVIE_MEDIA_V6_3\n"
    "from backend.services.storyboard.movie_visual_beat_planner import (\n"
    "    MovieVisualBeatPlanner,\n"
    ")\n"
    "from backend.services.video.movie_media_resolver import (\n"
    "    MovieMediaResolver,\n"
    ")\n"
)

if "RICH_V1_MOVIE_MEDIA_V6_3" not in source:
    if anchor not in source:
        raise RuntimeError("Import anchor not found.")
    source = source.replace(anchor, addition, 1)

# ------------------------------------------------------------
# 2. Initialize existing movie components
# ------------------------------------------------------------

anchor = (
    "        self.visual_beat_planner = VisualBeatPlanner()\n"
)

addition = (
    "        self.visual_beat_planner = VisualBeatPlanner()\n"
    "\n"
    "        # RICH_V1_MOVIE_MEDIA_V6_3\n"
    "        self.movie_visual_beat_planner = MovieVisualBeatPlanner()\n"
    "        self.movie_media_resolver = MovieMediaResolver()\n"
)

if "self.movie_visual_beat_planner = MovieVisualBeatPlanner()" not in source:
    if anchor not in source:
        raise RuntimeError("Initializer anchor not found.")
    source = source.replace(anchor, addition, 1)

# ------------------------------------------------------------
# 3. Replace generic visual-beat planning with a movie-only
#    branch while leaving every other format unchanged.
# ------------------------------------------------------------

old = '''        visual_beats = self.visual_beat_planner.plan(
            content=generated,
            topic=topic,
            genre=genre,
            format_name=(
                format_decision.format_name
            ),
        )

        if not visual_beats:
            raise RuntimeError(
                "VisualBeatPlanner produced no visual beats."
            )

        visual_beat_dicts = (
            self.visual_beat_planner.to_dicts(
                visual_beats
            )
        )
'''

new = '''        # RICH_V1_MOVIE_MEDIA_V6_3
        #
        # Famous-movie commentary uses its dedicated 14-beat
        # production grammar. Every other Rich V1 format retains
        # the existing generic VisualBeatPlanner unchanged.
        is_movie_commentary = (
            str(format_decision.format_name).strip()
            == "famous_movie_commentary"
        )

        movie_title = str(
            generated.metadata.get("movie_title", "")
            or trend.get("movie_title", "")
        ).strip()

        if is_movie_commentary:

            if not movie_title:
                raise RuntimeError(
                    "V6.3 movie production requires movie_title."
                )

            visual_beats = (
                self.movie_visual_beat_planner.plan(
                    content=generated,
                    movie_title=movie_title,
                    topic=topic,
                )
            )

            visual_beat_dicts = (
                self.movie_visual_beat_planner.to_dicts(
                    visual_beats
                )
            )

        else:

            visual_beats = self.visual_beat_planner.plan(
                content=generated,
                topic=topic,
                genre=genre,
                format_name=(
                    format_decision.format_name
                ),
            )

            visual_beat_dicts = (
                self.visual_beat_planner.to_dicts(
                    visual_beats
                )
            )

        if not visual_beats:
            raise RuntimeError(
                "Visual beat planner produced no visual beats."
            )
'''

if "is_movie_commentary = (" not in source:
    if old not in source:
        raise RuntimeError(
            "Visual-beat planning block did not match current source."
        )
    source = source.replace(old, new, 1)

PIPE.write_text(source, encoding="utf-8")

# ------------------------------------------------------------
# Verification
# ------------------------------------------------------------

checks = {
    "v63_marker":
        "RICH_V1_MOVIE_MEDIA_V6_3" in source,

    "movie_planner_import":
        "MovieVisualBeatPlanner" in source,

    "movie_resolver_import":
        "MovieMediaResolver" in source,

    "movie_planner_initialized":
        "self.movie_visual_beat_planner = MovieVisualBeatPlanner()"
        in source,

    "movie_resolver_initialized":
        "self.movie_media_resolver = MovieMediaResolver()"
        in source,

    "movie_format_branch":
        '"famous_movie_commentary"' in source
        and "is_movie_commentary" in source,

    "dedicated_movie_planner":
        "self.movie_visual_beat_planner.plan(" in source,

    "generic_planner_preserved":
        "self.visual_beat_planner.plan(" in source,

    "v61_preserved":
        "_v61_build_video_matches" in source,

    "v62_preserved":
        "_v62_acquire_source_footage" in source,

    "renderer_video_path_preserved":
        "beat_videos=v61_video_matches" in source,
}

try:
    py_compile.compile(
        str(PIPE),
        doraise=True,
    )
    compile_ok = True
except Exception as exc:
    compile_ok = False
    print("COMPILE ERROR:", repr(exc))

for name, ok in checks.items():
    print(f"{name}: {'PASS' if ok else 'FAIL'}")

print(
    "PATCHED COMPILE:",
    "PASS" if compile_ok else "FAIL",
)

all_ok = compile_ok and all(checks.values())

if not all_ok:
    shutil.copy2(BACKUP, PIPE)
    print()
    print("V6.3 INSTALL: FAIL")
    print("Automatic rollback completed.")
    sys.exit(1)

print()
print("V6.3 INSTALL: PASS")
print("MovieVisualBeatPlanner is connected to production.")
print("MovieMediaResolver is initialized.")
print("Generic Rich V1 planning remains intact.")
print("V6.1/V6.2 remain intact.")
