from pathlib import Path

path = Path(
    "backend/services/video_renderer/renderer.py"
)

lines = path.read_text(
    encoding="utf-8"
).splitlines()

needles = [
    "use_semantic_beats",
    "image_clips.append",
    "beat_images",
    "visual_beats",
    "raw_beat_durations",
]

hits = set()

for i, line in enumerate(lines):
    if any(
        needle in line
        for needle in needles
    ):
        hits.add(i)

print(
    f"FILE: {path}"
)

print(
    f"TOTAL LINES: {len(lines)}"
)

print()

for hit in sorted(hits):

    start = max(
        0,
        hit - 35,
    )

    end = min(
        len(lines),
        hit + 55,
    )

    print("=" * 78)
    print(
        f"CONTEXT AROUND LINE {hit + 1}"
    )
    print("=" * 78)

    for index in range(
        start,
        end,
    ):
        print(
            f"{index + 1:04d}: "
            f"{lines[index]}"
        )

    print()
