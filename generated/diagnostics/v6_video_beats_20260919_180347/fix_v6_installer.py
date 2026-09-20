from pathlib import Path

path = Path(
    r"generated/diagnostics/v6_video_beats_20260919_180347/install_v6.py"
)

text = path.read_text(encoding="utf-8")

old = '''    import_marker = "from __future__ import annotations"

    if "RICH_V1_VIDEO_BEATS_V6" in pipeline:
        print("V6 pipeline markers already installed.")
    else:
        # Insert only imports that are required for video indexing.
        insert_after = import_marker

        if insert_after not in pipeline:
            raise RuntimeError("Could not locate pipeline import anchor.")

        pipeline = pipeline.replace(
            insert_after,
            insert_after + """

# RICH_V1_VIDEO_BEATS_V6
from backend.services.video.source_clip_indexer import SourceClipIndexer
""",
            1,
        )
'''

new = '''    if "RICH_V1_VIDEO_BEATS_V6" in pipeline:
        print("V6 pipeline markers already installed.")
    else:
        # Do not depend on a specific module-header import.
        # Insert directly before the VideoPipeline class so the
        # import remains module-level regardless of current header.
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
'''

if old not in text:
    raise RuntimeError(
        "Expected original import-anchor block was not found "
        "in install_v6.py. No changes made."
    )

text = text.replace(
    old,
    new,
    1,
)

path.write_text(
    text,
    encoding="utf-8",
)

print("V6 installer import anchor corrected.")
