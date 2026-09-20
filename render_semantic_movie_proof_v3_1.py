"""Jarvis Rich V1 movie proof V3.1.

Adds:
- credits/end-section exclusion
- blur / darkness / flat-frame rejection
- semantic confidence floor
- duplicate-frame suppression
- face-aware crop safety
- multi-factor candidate scoring
"""

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
    "SEMANTIC_MOVIE_REFERENCE_PROOF_V3_1.mp4"
)

SHOT_DURATIONS = [
    1.2, 1.7, 1.4, 2.2, 1.0, 1.8,
    1.5, 2.0, 1.1, 1.6, 2.4, 1.3,
    1.9, 1.5, 2.1, 1.0, 1.8, 1.4,
    2.3, 1.2, 1.7, 2.9,
]

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

SEMANTIC_FLOOR = 0.175

# V3 selected credits around 708–717 sec.
# V3.1 never searches the final minute.
END_EXCLUSION_SECONDS = 65.0

MIN_BRIGHTNESS = 18.0
MAX_BRIGHTNESS = 238.0
MIN_CONTRAST = 18.0
MIN_BLUR_SCORE = 22.0

DUPLICATE_COSINE = 0.965


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

    print("CLIP DEVICE:", device)

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

    return model, preprocess, tokenizer, device


def visual_quality(frame):

    gray = (
        frame.astype(np.float32)
        .mean(axis=2)
    )

    brightness = float(
        gray.mean()
    )

    contrast = float(
        gray.std()
    )

    # Basic sharpness without requiring OCR.
    try:
        import cv2

        gray_u8 = cv2.cvtColor(
            frame,
            cv2.COLOR_RGB2GRAY,
        )

        blur_score = float(
            cv2.Laplacian(
                gray_u8,
                cv2.CV_64F,
            ).var()
        )

    except Exception:
        # Numpy gradient fallback.
        gx = np.diff(
            gray,
            axis=1,
        )
        gy = np.diff(
            gray,
            axis=0,
        )

        blur_score = float(
            np.var(gx)
            + np.var(gy)
        )

    valid = True
    reasons = []

    if brightness < MIN_BRIGHTNESS:
        valid = False
        reasons.append("too_dark")

    if brightness > MAX_BRIGHTNESS:
        valid = False
        reasons.append("too_bright")

    if contrast < MIN_CONTRAST:
        valid = False
        reasons.append("flat_frame")

    if blur_score < MIN_BLUR_SCORE:
        valid = False
        reasons.append("blurred")

    # Normalize quality roughly into 0..1.
    contrast_q = min(
        contrast / 65.0,
        1.0,
    )

    blur_q = min(
        blur_score / 250.0,
        1.0,
    )

    brightness_q = max(
        0.0,
        1.0
        - abs(
            brightness - 125.0
        ) / 125.0,
    )

    score = (
        contrast_q * 0.35
        + blur_q * 0.45
        + brightness_q * 0.20
    )

    return {
        "valid": valid,
        "reasons": reasons,
        "brightness": brightness,
        "contrast": contrast,
        "blur": blur_score,
        "quality_score": float(score),
    }


def detect_face_box(frame):

    try:
        import cv2

        gray = cv2.cvtColor(
            frame,
            cv2.COLOR_RGB2GRAY,
        )

        cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades
            + "haarcascade_frontalface_default.xml"
        )

        faces = cascade.detectMultiScale(
            gray,
            scaleFactor=1.08,
            minNeighbors=5,
            minSize=(35, 35),
        )

        if len(faces) == 0:
            return None

        x, y, w, h = max(
            faces,
            key=lambda box: (
                box[2] * box[3]
            ),
        )

        return (
            float(x),
            float(y),
            float(w),
            float(h),
        )

    except Exception:
        return None


def crop_safety(frame):

    face = detect_face_box(
        frame
    )

    if face is None:
        return {
            "has_face": False,
            "face_center_x": 0.5,
            "face_size": 0.0,
            "crop_score": 0.70,
        }

    x, y, w, h = face

    frame_h, frame_w = (
        frame.shape[:2]
    )

    center_x = (
        x + w / 2
    ) / frame_w

    face_area_ratio = (
        w * h
    ) / (
        frame_w * frame_h
    )

    # Penalize tiny faces and faces already hard against an edge.
    center_penalty = abs(
        center_x - 0.5
    )

    score = 1.0

    if face_area_ratio < 0.008:
        score -= 0.25

    if center_penalty > 0.38:
        score -= 0.25

    return {
        "has_face": True,
        "face_center_x": float(
            center_x
        ),
        "face_size": float(
            face_area_ratio
        ),
        "crop_score": max(
            0.0,
            score,
        ),
    }


def index_movie(
    source,
    preprocess,
    model,
    device,
):

    interval = 2.5

    start = 15.0

    end = max(
        start + 10,
        source.duration
        - END_EXCLUSION_SECONDS,
    )

    times = np.arange(
        start,
        end,
        interval,
    )

    print(
        "RAW CANDIDATE MOMENTS:",
        len(times),
    )

    kept_times = []
    kept_frames = []
    kept_quality = []
    kept_crop = []

    rejected = {
        "visual_quality": 0,
    }

    print()
    print(
        "========== QUALITY-GATING MOVIE =========="
    )

    for index, timestamp in enumerate(
        times,
        start=1,
    ):

        frame = source.get_frame(
            float(timestamp)
        ).astype(
            np.uint8
        )

        quality = visual_quality(
            frame
        )

        if not quality["valid"]:
            rejected[
                "visual_quality"
            ] += 1
            continue

        kept_times.append(
            float(timestamp)
        )

        kept_frames.append(
            preprocess(
                Image.fromarray(
                    frame
                ).convert(
                    "RGB"
                )
            )
        )

        kept_quality.append(
            quality
        )

        kept_crop.append(
            crop_safety(
                frame
            )
        )

        if index % 40 == 0:
            print(
                f"CHECKED: {index}/{len(times)}"
            )

    if not kept_frames:
        raise RuntimeError(
            "Quality gate rejected every frame."
        )

    print()
    print(
        "QUALITY REJECTED:",
        rejected["visual_quality"],
    )

    print(
        "QUALITY KEPT:",
        len(kept_frames),
    )

    ########################################################
    # Encode valid frames.
    ########################################################

    feature_batches = []

    for start_index in range(
        0,
        len(kept_frames),
        24,
    ):

        batch = torch.stack(
            kept_frames[
                start_index:
                start_index + 24
            ]
        ).to(
            device
        )

        with torch.no_grad():

            encoded = normalize(
                model.encode_image(
                    batch
                )
            )

        feature_batches.append(
            encoded.cpu()
        )

    features = torch.cat(
        feature_batches,
        dim=0,
    )

    return (
        np.array(
            kept_times,
            dtype=np.float32,
        ),
        features,
        kept_quality,
        kept_crop,
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


def choose_shots(
    times,
    image_features,
    text_features,
    qualities,
    crop_data,
):

    similarities = (
        text_features
        @ image_features.T
    ).numpy()

    selected = []
    used_indexes = set()

    print()
    print(
        "========== V3.1 QUALITY-AWARE SHOT PLAN =========="
    )

    for beat_index, beat in enumerate(
        VISUAL_BEATS
    ):

        semantic_scores = (
            similarities[
                beat_index
            ]
        )

        order = np.argsort(
            semantic_scores
        )[::-1]

        winner = None
        winner_score = -999.0

        for candidate_index in order[:35]:

            candidate_index = int(
                candidate_index
            )

            semantic = float(
                semantic_scores[
                    candidate_index
                ]
            )

            if semantic < SEMANTIC_FLOOR:
                continue

            if candidate_index in used_indexes:
                continue

            ################################################
            # Duplicate suppression against previous shots.
            ################################################

            duplicate = False

            for used in used_indexes:

                cosine = float(
                    (
                        image_features[
                            candidate_index
                        ]
                        @ image_features[
                            used
                        ]
                    ).item()
                )

                if cosine >= DUPLICATE_COSINE:
                    duplicate = True
                    break

            if duplicate:
                continue

            quality_score = float(
                qualities[
                    candidate_index
                ][
                    "quality_score"
                ]
            )

            crop_score = float(
                crop_data[
                    candidate_index
                ][
                    "crop_score"
                ]
            )

            ################################################
            # Encourage chronology, but semantic relevance
            # can still override position.
            ################################################

            desired_position = (
                beat_index
                / max(
                    len(VISUAL_BEATS) - 1,
                    1,
                )
            )

            actual_position = (
                candidate_index
                / max(
                    len(times) - 1,
                    1,
                )
            )

            continuity_score = max(
                0.0,
                1.0
                - abs(
                    desired_position
                    - actual_position
                ),
            )

            final_score = (
                semantic * 0.50
                + quality_score * 0.20
                + crop_score * 0.15
                + continuity_score * 0.15
            )

            if final_score > winner_score:

                winner_score = (
                    final_score
                )

                winner = (
                    candidate_index
                )

        if winner is None:
            raise RuntimeError(
                "No acceptable shot for beat "
                f"{beat_index + 1}: {beat}"
            )

        used_indexes.add(
            winner
        )

        semantic = float(
            similarities[
                beat_index,
                winner,
            ]
        )

        selected.append(
            winner
        )

        print(
            f"{beat_index + 1:02d}",
            "|",
            round(
                float(times[winner]),
                2,
            ),
            "sec",
            "| SEM:",
            round(
                semantic,
                4,
            ),
            "| Q:",
            round(
                qualities[winner][
                    "quality_score"
                ],
                3,
            ),
            "| CROP:",
            round(
                crop_data[winner][
                    "crop_score"
                ],
                3,
            ),
            "|",
            beat,
        )

    return selected


def verticalize(
    clip,
    *,
    face_center_x: float,
    face_size: float,
):

    scale = max(
        WIDTH / clip.w,
        HEIGHT / clip.h,
    )

    clip = clip.resized(
        scale
    )

    ########################################################
    # Avoid V3's excessive face punch-ins.
    ########################################################

    zoom = 1.0

    if (
        face_size > 0
        and face_size < 0.025
    ):
        zoom = 1.025

    if zoom != 1.0:
        clip = clip.resized(
            zoom
        )

    desired_x = (
        clip.w
        * face_center_x
    )

    half_width = (
        WIDTH / 2
    )

    desired_x = max(
        half_width,
        min(
            clip.w - half_width,
            desired_x,
        ),
    )

    return clip.cropped(
        x_center=desired_x,
        y_center=clip.h / 2,
        width=WIDTH,
        height=HEIGHT,
    )


def main():

    config = (
        RuntimeConfig.from_environment()
    )

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

    source = VideoFileClip(
        str(SOURCE)
    )

    print(
        "SOURCE:",
        SOURCE,
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
        times,
        image_features,
        qualities,
        crop_data,
    ) = index_movie(
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

    selected = choose_shots(
        times,
        image_features,
        text_features,
        qualities,
        crop_data,
    )

    clips = []
    captions = []

    base = None
    final = None

    try:

        for shot_index, (
            candidate_index,
            duration,
        ) in enumerate(
            zip(
                selected,
                SHOT_DURATIONS,
            )
        ):

            timestamp = float(
                times[
                    candidate_index
                ]
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

            if end - start < duration:
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

            crop = crop_data[
                candidate_index
            ]

            shot = verticalize(
                shot,
                face_center_x=(
                    crop[
                        "face_center_x"
                    ]
                ),
                face_size=(
                    crop[
                        "face_size"
                    ]
                ),
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

        timeline = 0.0

        for index, duration in enumerate(
            SHOT_DURATIONS
        ):

            if index in CAPTION_BEATS:

                caption = (
                    TextClip(
                        text=(
                            CAPTION_BEATS[
                                index
                            ]
                        ),
                        font_size=74,
                        color="white",
                        stroke_color="black",
                        stroke_width=4,
                        method="caption",
                        size=(
                            820,
                            None,
                        ),
                        text_align="center",
                    )
                    .with_start(
                        timeline
                    )
                    .with_duration(
                        min(
                            duration,
                            1.5,
                        )
                    )
                    .with_position(
                        (
                            "center",
                            1120,
                        )
                    )
                )

                captions.append(
                    caption
                )

            timeline += duration

        final = CompositeVideoClip(
            [
                base,
                *captions,
            ],
            size=(
                WIDTH,
                HEIGHT,
            ),
        ).with_duration(
            37.0
        )

        print()
        print(
            "========== RENDERING V3.1 =========="
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
            "========== V3.1 COMPLETE =========="
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
