"""Semantic real-movie proof V3 for Jarvis Rich V1."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import open_clip
import torch
from PIL import Image

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
    "SEMANTIC_MOVIE_REFERENCE_PROOF_V3.mp4"
)

# Reference movie-facts rhythm.
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

# These describe VISUAL requirements, not timestamps.
VISUAL_BEATS = [
    "cinematic futuristic city establishing shot",
    "woman face cinematic close up",
    "man face dramatic cinematic close up",
    "two characters having an emotional conversation",
    "futuristic technology detail close up",
    "character reacting with concern",
    "wide science fiction environment",
    "mechanical machine or robot detail",
    "character looking intensely at something",
    "dramatic futuristic interior",
    "science fiction machinery operating",
    "woman dramatic reaction shot",
    "man dramatic reaction shot",
    "large futuristic machine",
    "characters interacting in science fiction environment",
    "extreme close up cinematic face",
    "robot or mechanical action",
    "dramatic action scene",
    "large scale science fiction visual",
    "character reaction during action",
    "cinematic climax action",
    "dramatic final movie shot",
]

CAPTION_BEATS = {
    0: "LOOK CLOSELY",
    3: "THIS MATTERS",
    7: "WATCH THE MACHINE",
    11: "NOTICE HER REACTION",
    15: "LOOK AT HIS FACE",
    18: "THEN THIS HAPPENS",
    20: "WATCH THIS",
}


def normalize(features):
    return features / features.norm(
        dim=-1,
        keepdim=True,
    )


def load_clip():

    device = (
        "cuda"
        if torch.cuda.is_available()
        else "cpu"
    )

    print(
        "CLIP DEVICE:",
        device,
    )

    model, _, preprocess = (
        open_clip.create_model_and_transforms(
            "ViT-B-32",
            pretrained="laion2b_s34b_b79k",
            device=device,
        )
    )

    tokenizer = open_clip.get_tokenizer(
        "ViT-B-32"
    )

    model.eval()

    return (
        model,
        preprocess,
        tokenizer,
        device,
    )


def sample_movie(
    source,
    preprocess,
    model,
    device,
):

    # Around 230 candidate moments for a 12 minute film.
    interval = 3.0

    start = 15.0
    end = source.duration - 15.0

    times = np.arange(
        start,
        end,
        interval,
    )

    print(
        "CANDIDATE MOMENTS:",
        len(times),
    )

    features = []

    batch_images = []
    batch_times = []

    def flush():

        if not batch_images:
            return

        tensor = torch.stack(
            batch_images
        ).to(
            device
        )

        with torch.no_grad():

            encoded = normalize(
                model.encode_image(
                    tensor
                )
            )

        features.append(
            encoded.cpu()
        )

        batch_images.clear()
        batch_times.clear()

    print()
    print(
        "========== INDEXING MOVIE =========="
    )

    for index, timestamp in enumerate(
        times,
        start=1,
    ):

        frame = source.get_frame(
            float(timestamp)
        )

        image = Image.fromarray(
            frame.astype(
                np.uint8
            )
        ).convert(
            "RGB"
        )

        batch_images.append(
            preprocess(
                image
            )
        )

        batch_times.append(
            timestamp
        )

        if (
            len(batch_images) >= 24
            or index == len(times)
        ):
            flush()

        if (
            index % 30 == 0
            or index == len(times)
        ):
            print(
                f"INDEXED: {index}/{len(times)}"
            )

    return (
        times,
        torch.cat(
            features,
            dim=0,
        ),
    )


def embed_prompts(
    model,
    tokenizer,
    device,
):

    tokens = tokenizer(
        VISUAL_BEATS
    ).to(
        device
    )

    with torch.no_grad():

        features = normalize(
            model.encode_text(
                tokens
            )
        )

    return features.cpu()


def select_semantic_timeline(
    candidate_times,
    image_features,
    text_features,
):

    similarity = (
        text_features
        @ image_features.T
    ).numpy()

    beat_count = len(
        VISUAL_BEATS
    )

    candidate_count = len(
        candidate_times
    )

    ########################################################
    # Position regularization:
    # encourage story progression through the film while
    # still allowing CLIP to choose the strongest scene.
    ########################################################

    normalized_times = (
        candidate_times
        - candidate_times[0]
    ) / (
        candidate_times[-1]
        - candidate_times[0]
    )

    for beat in range(
        beat_count
    ):

        target_position = (
            beat
            / max(
                beat_count - 1,
                1,
            )
        )

        position_penalty = (
            np.abs(
                normalized_times
                - target_position
            )
            * 0.045
        )

        similarity[
            beat
        ] -= position_penalty

    ########################################################
    # Dynamic programming:
    # choose an ordered sequence rather than random scenes.
    ########################################################

    negative = -1e9

    dp = np.full(
        (
            beat_count,
            candidate_count,
        ),
        negative,
        dtype=np.float32,
    )

    parent = np.full(
        (
            beat_count,
            candidate_count,
        ),
        -1,
        dtype=np.int32,
    )

    dp[0] = similarity[0]

    # Require at least ~6 seconds separation between
    # selected candidate centers.
    minimum_gap = 2

    for beat in range(
        1,
        beat_count,
    ):

        best_score = negative
        best_index = -1

        prefix_scores = np.full(
            candidate_count,
            negative,
            dtype=np.float32,
        )

        prefix_indexes = np.full(
            candidate_count,
            -1,
            dtype=np.int32,
        )

        for index in range(
            candidate_count
        ):

            previous = (
                index
                - minimum_gap
            )

            if previous >= 0:

                candidate_score = dp[
                    beat - 1,
                    previous,
                ]

                if (
                    candidate_score
                    > best_score
                ):
                    best_score = (
                        candidate_score
                    )

                    best_index = (
                        previous
                    )

            prefix_scores[
                index
            ] = best_score

            prefix_indexes[
                index
            ] = best_index

        for index in range(
            candidate_count
        ):

            if (
                prefix_indexes[
                    index
                ]
                < 0
            ):
                continue

            dp[
                beat,
                index,
            ] = (
                prefix_scores[
                    index
                ]
                + similarity[
                    beat,
                    index,
                ]
            )

            parent[
                beat,
                index,
            ] = prefix_indexes[
                index
            ]

    final_index = int(
        np.argmax(
            dp[-1]
        )
    )

    selected_indexes = [
        final_index
    ]

    for beat in range(
        beat_count - 1,
        0,
        -1,
    ):

        final_index = int(
            parent[
                beat,
                final_index,
            ]
        )

        selected_indexes.append(
            final_index
        )

    selected_indexes.reverse()

    selected = []

    print()
    print(
        "========== SEMANTIC SHOT PLAN =========="
    )

    for beat, candidate_index in enumerate(
        selected_indexes
    ):

        timestamp = float(
            candidate_times[
                candidate_index
            ]
        )

        score = float(
            (
                text_features[
                    beat
                ]
                @ image_features[
                    candidate_index
                ]
            ).item()
        )

        selected.append(
            (
                timestamp,
                score,
            )
        )

        print(
            f"{beat + 1:02d}",
            "|",
            round(
                timestamp,
                2,
            ),
            "sec",
            "|",
            round(
                score,
                4,
            ),
            "|",
            VISUAL_BEATS[
                beat
            ],
        )

    return selected


def detect_face_center(
    frame,
):

    try:
        import cv2
    except Exception:
        return None

    try:

        gray = cv2.cvtColor(
            frame,
            cv2.COLOR_RGB2GRAY,
        )

        cascade = (
            cv2.CascadeClassifier(
                cv2.data.haarcascades
                + "haarcascade_frontalface_default.xml"
            )
        )

        faces = cascade.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=4,
            minSize=(
                35,
                35,
            ),
        )

        if len(faces) == 0:
            return None

        largest = max(
            faces,
            key=lambda face: (
                face[2]
                * face[3]
            ),
        )

        x, y, w, h = largest

        return (
            x + w / 2
        )

    except Exception:
        return None


def verticalize(
    clip,
    source,
    timestamp,
    shot_index,
):

    ########################################################
    # Find important horizontal position.
    ########################################################

    frame = source.get_frame(
        timestamp
    )

    face_center = detect_face_center(
        frame
    )

    if face_center is None:

        normalized_x = 0.5

    else:

        normalized_x = (
            face_center
            / frame.shape[1]
        )

    ########################################################
    # Scale to vertical canvas.
    ########################################################

    scale = max(
        WIDTH / clip.w,
        HEIGHT / clip.h,
    )

    clip = clip.resized(
        scale
    )

    zoom_pattern = (
        1.00,
        1.035,
        1.02,
        1.05,
        1.00,
    )

    zoom = zoom_pattern[
        shot_index
        % len(
            zoom_pattern
        )
    ]

    if zoom != 1.0:

        clip = clip.resized(
            zoom
        )

    desired_x = (
        clip.w
        * normalized_x
    )

    half_width = (
        WIDTH / 2
    )

    desired_x = max(
        half_width,
        min(
            clip.w
            - half_width,
            desired_x,
        ),
    )

    clip = clip.cropped(
        x_center=desired_x,
        y_center=clip.h / 2,
        width=WIDTH,
        height=HEIGHT,
    )

    return clip


def main():

    config = RuntimeConfig.from_environment()

    configure_moviepy_ffmpeg(
        config.ffmpeg_executable
    )

    if not SOURCE.is_file():

        raise FileNotFoundError(
            SOURCE
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
        str(
            SOURCE
        )
    )

    print(
        "SOURCE DURATION:",
        round(
            source.duration,
            3,
        ),
    )

    (
        model,
        preprocess,
        tokenizer,
        device,
    ) = load_clip()

    (
        candidate_times,
        image_features,
    ) = sample_movie(
        source,
        preprocess,
        model,
        device,
    )

    text_features = embed_prompts(
        model,
        tokenizer,
        device,
    )

    selected = select_semantic_timeline(
        candidate_times,
        image_features,
        text_features,
    )

    clips = []
    captions = []

    base = None
    final = None

    try:

        ####################################################
        # Build actual selected shots.
        ####################################################

        for index, (
            selection,
            duration,
        ) in enumerate(
            zip(
                selected,
                SHOT_DURATIONS,
            )
        ):

            timestamp, score = (
                selection
            )

            start = max(
                0.0,
                timestamp
                - duration / 2
            )

            end = min(
                source.duration,
                start + duration,
            )

            if (
                end - start
                < duration
            ):

                start = max(
                    0.0,
                    end - duration,
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
                source,
                timestamp,
                index,
            )

            shot = shot.with_duration(
                duration
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
        # Caption timing follows shot boundaries.
        ####################################################

        timeline_position = 0.0

        for index, duration in enumerate(
            SHOT_DURATIONS
        ):

            if index in CAPTION_BEATS:

                text = CAPTION_BEATS[
                    index
                ]

                caption = (
                    TextClip(
                        text=text,
                        font_size=78,
                        color="white",
                        stroke_color="black",
                        stroke_width=5,
                        method="caption",
                        size=(
                            860,
                            None,
                        ),
                        text_align="center",
                    )
                    .with_start(
                        timeline_position
                    )
                    .with_duration(
                        min(
                            duration,
                            1.8,
                        )
                    )
                    .with_position(
                        (
                            "center",
                            1080,
                        )
                    )
                )

                captions.append(
                    caption
                )

            timeline_position += (
                duration
            )

        final = CompositeVideoClip(
            [
                base,
                *captions,
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
            "========== RENDERING SEMANTIC MOVIE V3 =========="
        )

        final.write_videofile(
            str(
                OUTPUT
            ),
            fps=FPS,
            codec="libx264",
            audio=False,
            preset="medium",
            logger=None,
        )

        print()
        print(
            "========== SEMANTIC MOVIE V3 COMPLETE =========="
        )

        print(
            "VIDEO:",
            OUTPUT,
        )

        print(
            "SHOTS:",
            len(
                clips
            ),
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

        for caption in captions:

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
