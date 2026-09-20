"""Modern real-footage movie proof for Jarvis Rich V1."""

from __future__ import annotations

from pathlib import Path

from moviepy import (
    CompositeVideoClip,
    TextClip,
    VideoFileClip,
    concatenate_videoclips,
)

from backend.services.runtime.runtime_config import RuntimeConfig
from backend.services.video_renderer.moviepy_runtime import (
    configure_moviepy_ffmpeg,
)


WIDTH = 1080
HEIGHT = 1920
FPS = 60

SOURCE = Path(
    "generated/licensed_media/"
    "legal-modern-movie-test/"
    "Tears_of_Steel_720p.mov"
)

OUTPUT = Path(
    "generated/videos/"
    "MODERN_MOVIE_REFERENCE_PROOF_V2.mp4"
)

# 22 shots, total 37 seconds.
SHOT_DURATIONS = [
    1.2,
    1.7,
    1.4,
    2.2,
    1.0,
    1.8,
    1.5,
    2.0,
    1.1,
    1.6,
    2.4,
    1.3,
    1.9,
    1.5,
    2.1,
    1.0,
    1.8,
    1.4,
    2.3,
    1.2,
    1.7,
    2.9,
]

CAPTIONS = [
    (
        0.0,
        2.5,
        "YOU PROBABLY MISSED\nTHIS DETAIL",
    ),
    (
        8.0,
        10.2,
        "LOOK AT WHAT\nHAPPENS HERE",
    ),
    (
        17.5,
        20.0,
        "THIS CHANGES\nTHE SCENE",
    ),
    (
        27.0,
        29.5,
        "WATCH THE\nBACKGROUND",
    ),
]


def verticalize(
    clip,
    shot_index: int,
):

    scale = max(
        WIDTH / clip.w,
        HEIGHT / clip.h,
    )

    clip = clip.resized(
        scale
    )

    zoom_pattern = (
        1.00,
        1.045,
        1.02,
        1.07,
        1.00,
        1.035,
    )

    zoom = zoom_pattern[
        shot_index
        % len(zoom_pattern)
    ]

    if zoom != 1.0:
        clip = clip.resized(
            zoom
        )

    x_offsets = (
        0.00,
        -0.035,
        0.03,
        0.00,
        -0.02,
        0.025,
    )

    offset_ratio = x_offsets[
        shot_index
        % len(x_offsets)
    ]

    x_center = (
        clip.w / 2
        + clip.w * offset_ratio
    )

    half_width = WIDTH / 2

    x_center = max(
        half_width,
        min(
            clip.w - half_width,
            x_center,
        ),
    )

    return clip.cropped(
        x_center=x_center,
        y_center=clip.h / 2,
        width=WIDTH,
        height=HEIGHT,
    )


def main():

    config = RuntimeConfig.from_environment()

    configure_moviepy_ffmpeg(
        config.ffmpeg_executable
    )

    if not SOURCE.is_file():
        raise FileNotFoundError(
            f"Modern movie source not found: {SOURCE}"
        )

    OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    print(
        "SOURCE:",
        SOURCE,
    )

    source = VideoFileClip(
        str(SOURCE)
    )

    print(
        "SOURCE DURATION:",
        round(source.duration, 3),
    )

    print(
        "SOURCE SIZE:",
        source.size,
    )

    print(
        "SOURCE FPS:",
        source.fps,
    )

    clips = []
    caption_clips = []

    base = None
    final = None

    try:

        ####################################################
        # Spread clips across modern film.
        ####################################################

        safe_start = min(
            35.0,
            source.duration * 0.08,
        )

        safe_end = min(
            source.duration - 10.0,
            source.duration * 0.92,
        )

        usable_span = (
            safe_end
            - safe_start
        )

        count = len(
            SHOT_DURATIONS
        )

        for index, duration in enumerate(
            SHOT_DURATIONS
        ):

            ratio = (
                index
                / max(
                    count - 1,
                    1,
                )
            )

            start = (
                safe_start
                + usable_span * ratio
            )

            if (
                start + duration
                > source.duration
            ):
                start = max(
                    0.0,
                    source.duration - duration
                )

            shot = source.subclipped(
                start,
                start + duration,
            )

            shot = shot.with_audio(
                None
            )

            shot = verticalize(
                shot,
                index,
            )

            speed_pattern = (
                1.00,
                1.04,
                0.97,
                1.00,
                1.06,
            )

            speed = speed_pattern[
                index
                % len(speed_pattern)
            ]

            if speed != 1.0:

                shot = (
                    shot
                    .with_speed_scaled(
                        speed
                    )
                    .with_duration(
                        duration
                    )
                )

            clips.append(
                shot
            )

        base = concatenate_videoclips(
            clips,
            method="compose",
        )

        base = base.with_duration(
            37.0
        )

        ####################################################
        # Captions
        ####################################################

        for start, end, text in CAPTIONS:

            caption = (
                TextClip(
                    text=text,
                    font_size=82,
                    color="white",
                    stroke_color="black",
                    stroke_width=6,
                    method="caption",
                    size=(
                        880,
                        None,
                    ),
                    text_align="center",
                )
                .with_start(
                    start
                )
                .with_duration(
                    end - start
                )
                .with_position(
                    (
                        "center",
                        1050,
                    )
                )
            )

            caption_clips.append(
                caption
            )

        final = CompositeVideoClip(
            [
                base,
                *caption_clips,
            ],
            size=(
                WIDTH,
                HEIGHT,
            ),
        )

        final = final.with_duration(
            37.0
        )

        print()
        print(
            "========== RENDERING MODERN MOVIE PROOF V2 =========="
        )

        final.write_videofile(
            str(OUTPUT),
            fps=FPS,
            codec="libx264",
            audio=False,
            preset="medium",
            logger=None,
        )

        print()
        print(
            "========== MODERN MOVIE PROOF V2 COMPLETE =========="
        )

        print(
            "VIDEO:",
            OUTPUT,
        )

        print(
            "SHOTS:",
            len(clips),
        )

        print(
            "DURATION:",
            37.0,
        )

        print(
            "RESOLUTION:",
            f"{WIDTH}x{HEIGHT}",
        )

        print(
            "FPS:",
            FPS,
        )

    finally:

        if final is not None:
            final.close()

        if base is not None:
            base.close()

        for caption in caption_clips:
            try:
                caption.close()
            except Exception:
                pass

        for clip in clips:
            try:
                clip.close()
            except Exception:
                pass

        source.close()


if __name__ == "__main__":
    main()
