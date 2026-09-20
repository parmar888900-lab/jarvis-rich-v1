"""Jarvis Rich V1 â€” surgical polish editor V10."""

from __future__ import annotations
import re

import subprocess
from pathlib import Path

import cv2
import numpy as np
import open_clip
import torch
from PIL import Image

from moviepy import (
    AudioFileClip,
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
TARGET_DURATION = 37.0

SOURCE = Path(
    "generated/licensed_media/"
    "legal-modern-movie-test/"
    "Tears_of_Steel_720p.mov"
)

OUTPUT = Path(
    "generated/videos/"
    "NARRATIVE_MOVIE_REFERENCE_PROOF_V13.mp4"
)

VOICE_OUTPUT = Path(
    "generated/audio/"
    "narrative_movie_v13.wav"
)

# Avoid the film's credits entirely for this benchmark.
SEARCH_START = 20.0
SEARCH_END = 580.0

# V5 ranking / QA.
LOCAL_SAMPLE_COUNT = 13

MIN_LOCAL_SEMANTIC = 0.145
MIN_LOCAL_QUALITY = 0.22

MAX_NEAR_DUPLICATE = 0.935

ENERGY_CURVE = (
    0.20, 0.22, 0.24, 0.28, 0.30, 0.34,
    0.37, 0.40, 0.43, 0.47, 0.50, 0.54,
    0.58, 0.62, 0.67, 0.72, 0.77, 0.82,
    0.87, 0.91, 0.96, 1.00,
)

SHOT_DURATIONS = [
    1.2, 1.7, 1.4, 2.2, 1.0, 1.8,
    1.5, 2.0, 1.1, 1.6, 2.4, 1.3,
    1.9, 1.5, 2.1, 1.0, 1.8, 1.4,
    2.3, 1.2, 1.7, 2.9,
]

NARRATION = (
    "They thought this meeting would be simple. "
    "Then the machines started waking up. "
    "Within moments, the city around them changed from a place to talk "
    "into something they had to survive. "
    "Every warning came too late. "
    "The machines kept moving, the danger kept growing, "
    "and suddenly there was nowhere left to hide. "
    "By the time the real threat appeared, running was the only choice."
)

V13_NARRATION = NARRATION
V13_STORY_SEGMENTS = []

# These now form one coherent visual story rather than 22 unrelated prompts.
VISUAL_BEATS = [
    "wide cinematic futuristic city establishing shot",
    "two people meeting in a futuristic environment",
    "woman watching a man closely cinematic medium shot",
    "man speaking during an emotional conversation",
    "woman listening serious reaction close up",
    "futuristic device or technology close up",
    "technology beginning to activate",
    "mechanical machinery moving",
    "character noticing something is wrong",
    "woman concerned reaction shot",
    "man looking toward danger",
    "wide futuristic environment becoming threatening",
    "large machine or robot appearing",
    "mechanical robot detail cinematic close up",
    "characters reacting to approaching danger",
    "extreme cinematic face reaction",
    "robot or machine moving aggressively",
    "characters during science fiction action",
    "large scale danger wide shot",
    "intense character reaction during action",
    "cinematic science fiction climax action",
    "dramatic final character or action shot",
]

CAPTIONS = {
    0: "AT FIRST...",
    4: "SOMETHING IS WRONG",
    7: "THEN IT ACTIVATES",
    12: "THE SCALE CHANGES",
    16: "NOW WATCH THIS",
    19: "EVERY REACTION MATTERS",
}


def normalize(x):
    return x / x.norm(
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

    return (
        model,
        preprocess,
        tokenizer,
        device,
    )


def frame_histogram(frame):

    hsv = cv2.cvtColor(
        frame,
        cv2.COLOR_RGB2HSV,
    )

    hist = cv2.calcHist(
        [hsv],
        [0, 1],
        None,
        [32, 32],
        [0, 180, 0, 256],
    )

    cv2.normalize(
        hist,
        hist,
    )

    return hist


def detect_scenes(source):

    print()
    print("========== DETECTING MOVIE SCENES ==========")

    step = 1.0
    threshold = 0.48

    times = np.arange(
        SEARCH_START,
        min(
            SEARCH_END,
            source.duration - 5,
        ),
        step,
    )

    boundaries = [
        float(times[0])
    ]

    previous_hist = None

    for index, timestamp in enumerate(
        times
    ):

        frame = source.get_frame(
            float(timestamp)
        ).astype(
            np.uint8
        )

        hist = frame_histogram(
            frame
        )

        if previous_hist is not None:

            correlation = cv2.compareHist(
                previous_hist,
                hist,
                cv2.HISTCMP_CORREL,
            )

            if correlation < threshold:

                if (
                    timestamp
                    - boundaries[-1]
                    >= 1.2
                ):
                    boundaries.append(
                        float(timestamp)
                    )

        previous_hist = hist

        if (
            index % 80 == 0
            and index > 0
        ):
            print(
                f"SCANNED: {index}/{len(times)}"
            )

    boundaries.append(
        min(
            SEARCH_END,
            source.duration - 5,
        )
    )

    scenes = []

    for start, end in zip(
        boundaries,
        boundaries[1:],
    ):

        duration = (
            end - start
        )

        if duration < 1.0:
            continue

        if duration > 15.0:

            divisions = int(
                np.ceil(
                    duration / 8.0
                )
            )

            segment = (
                duration / divisions
            )

            for part in range(
                divisions
            ):

                sub_start = (
                    start
                    + part * segment
                )

                sub_end = min(
                    end,
                    sub_start + segment,
                )

                scenes.append(
                    (
                        sub_start,
                        sub_end,
                    )
                )

        else:

            scenes.append(
                (
                    start,
                    end,
                )
            )

    print(
        "SCENES:",
        len(scenes),
    )

    return scenes


def quality_score(frame):

    gray = cv2.cvtColor(
        frame,
        cv2.COLOR_RGB2GRAY,
    )

    brightness = float(
        gray.mean()
    )

    contrast = float(
        gray.std()
    )

    sharpness = float(
        cv2.Laplacian(
            gray,
            cv2.CV_64F,
        ).var()
    )

    if brightness < 15:
        return None

    if brightness > 242:
        return None

    if contrast < 16:
        return None

    if sharpness < 20:
        return None

    brightness_score = max(
        0.0,
        1.0
        - abs(
            brightness - 120
        ) / 120,
    )

    return min(
        1.0,
        (
            min(
                contrast / 65,
                1.0,
            )
            * 0.35
            +
            min(
                sharpness / 250,
                1.0,
            )
            * 0.45
            +
            brightness_score
            * 0.20
        ),
    )


def detect_faces(frame):
    """
    Best-effort face detection.

    Some OpenCV builds do not expose the legacy Haar
    CascadeClassifier API. Face detection is therefore
    optional: focus_x() will fall back to visual-detail
    centering when it is unavailable.
    """

    if not hasattr(
        cv2,
        "CascadeClassifier",
    ):
        return []

    if not hasattr(
        cv2,
        "data",
    ):
        return []

    try:

        cascade_path = (
            cv2.data.haarcascades
            + "haarcascade_frontalface_default.xml"
        )

        cascade = cv2.CascadeClassifier(
            cascade_path
        )

        if (
            hasattr(
                cascade,
                "empty",
            )
            and cascade.empty()
        ):
            return []

        gray = cv2.cvtColor(
            frame,
            cv2.COLOR_RGB2GRAY,
        )

        faces = cascade.detectMultiScale(
            gray,
            scaleFactor=1.08,
            minNeighbors=5,
            minSize=(35, 35),
        )

        return list(
            faces
        )

    except Exception as exc:

        print(
            "FACE DETECTION FALLBACK:",
            type(exc).__name__,
        )

        return []


def focus_x(frame):

    faces = detect_faces(
        frame
    )

    h, w = frame.shape[:2]

    if faces:

        # Use group center for multiple actors rather than
        # cutting one actor out of a conversation.
        centers = [
            x + fw / 2
            for x, y, fw, fh
            in faces
        ]

        return float(
            np.mean(
                centers
            )
            / w
        )

    # Fallback: center the strongest visual-detail region.
    gray = cv2.cvtColor(
        frame,
        cv2.COLOR_RGB2GRAY,
    )

    edges = cv2.Sobel(
        gray,
        cv2.CV_32F,
        1,
        0,
        ksize=3,
    )

    energy = np.abs(
        edges
    ).sum(
        axis=0
    )

    if energy.sum() <= 0:

        return 0.5

    xs = np.arange(
        w,
        dtype=np.float32,
    )

    center = float(
        (
            xs * energy
        ).sum()
        / energy.sum()
    )

    return max(
        0.15,
        min(
            0.85,
            center / w,
        ),
    )


def index_scenes(
    source,
    scenes,
    model,
    preprocess,
    device,
):

    print()
    print("========== UNDERSTANDING SCENES ==========")

    entries = []
    tensors = []

    for index, (
        start,
        end,
    ) in enumerate(
        scenes,
        start=1,
    ):

        duration = (
            end - start
        )

        sample_times = [
            start + duration * 0.30,
            start + duration * 0.50,
            start + duration * 0.70,
        ]

        valid_tensors = []
        qualities = []
        focus_values = []

        for timestamp in sample_times:

            frame = source.get_frame(
                timestamp
            ).astype(
                np.uint8
            )

            quality = quality_score(
                frame
            )

            if quality is None:
                continue

            valid_tensors.append(
                preprocess(
                    Image.fromarray(
                        frame
                    ).convert(
                        "RGB"
                    )
                )
            )

            qualities.append(
                quality
            )

            focus_values.append(
                focus_x(
                    frame
                )
            )

        if not valid_tensors:
            continue

        entries.append(
            {
                "start": float(start),
                "end": float(end),
                "center": float(
                    start
                    + duration / 2
                ),
                "quality": float(
                    np.mean(
                        qualities
                    )
                ),
                "focus_x": float(
                    np.mean(
                        focus_values
                    )
                ),
            }
        )

        tensors.append(
            valid_tensors
        )

        if index % 30 == 0:

            print(
                f"ANALYZED: {index}/{len(scenes)}"
            )

    if not entries:
        raise RuntimeError(
            "No usable scenes."
        )

    embeddings = []

    for tensor_group in tensors:

        tensor = torch.stack(
            tensor_group
        ).to(
            device
        )

        with torch.no_grad():

            encoded = normalize(
                model.encode_image(
                    tensor
                )
            )

            averaged = encoded.mean(
                dim=0,
                keepdim=True,
            )

            averaged = normalize(
                averaged
            )

        embeddings.append(
            averaged.cpu()
        )

    return (
        entries,
        torch.cat(
            embeddings,
            dim=0,
        ),
    )


def text_embeddings(
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

        return normalize(
            model.encode_text(
                tokens
            )
        ).cpu()


def choose_story(
    entries,
    scene_features,
    text_features,
):
    """
    Globally optimize the complete 22-shot narrative.

    V4 originally selected shots greedily. That allowed
    early beats to jump too far forward in the movie and
    leave no footage for later beats.

    This version plans the full sequence together.
    """

    similarity = (
        text_features
        @ scene_features.T
    ).numpy()

    beat_count = len(
        VISUAL_BEATS
    )

    scene_count = len(
        entries
    )

    if scene_count < beat_count:
        raise RuntimeError(
            "Not enough indexed scenes for story."
        )

    print()
    print(
        "========== GLOBAL NARRATIVE PLANNER =========="
    )

    ########################################################
    # Per-beat / per-scene score matrix.
    ########################################################

    scores = np.full(
        (
            beat_count,
            scene_count,
        ),
        -1e9,
        dtype=np.float32,
    )

    search_span = max(
        SEARCH_END
        - SEARCH_START,
        1.0,
    )

    for beat_index in range(
        beat_count
    ):

        expected_position = (
            beat_index
            / max(
                beat_count - 1,
                1,
            )
        )

        for scene_index, entry in enumerate(
            entries
        ):

            semantic = float(
                similarity[
                    beat_index,
                    scene_index,
                ]
            )

            # Soft floor rather than hard rejection.
            # Weak semantic matches remain possible but
            # receive a substantial penalty.
            semantic_penalty = 0.0

            if semantic < 0.16:
                semantic_penalty = (
                    0.16 - semantic
                ) * 1.5

            actual_position = (
                entry["center"]
                - SEARCH_START
            ) / search_span

            chronology = max(
                0.0,
                1.0
                - abs(
                    actual_position
                    - expected_position
                ),
            )

            quality = float(
                entry[
                    "quality"
                ]
            )

            score = (
                semantic * 0.58
                + quality * 0.22
                + chronology * 0.20
                - semantic_penalty
            )

            scores[
                beat_index,
                scene_index,
            ] = score

    ########################################################
    # Dynamic programming.
    #
    # Every beat must move forward through the movie, but
    # the entire 22-shot sequence is planned globally.
    ########################################################

    negative = -1e9

    dp = np.full(
        (
            beat_count,
            scene_count,
        ),
        negative,
        dtype=np.float32,
    )

    parent = np.full(
        (
            beat_count,
            scene_count,
        ),
        -1,
        dtype=np.int32,
    )

    ########################################################
    # Do not let the first beat start too late.
    ########################################################

    for scene_index in range(
        scene_count
    ):

        remaining_scenes = (
            scene_count
            - scene_index
        )

        if remaining_scenes < beat_count:
            continue

        dp[
            0,
            scene_index,
        ] = scores[
            0,
            scene_index,
        ]

    ########################################################
    # Require progression while preserving enough future
    # scenes for all remaining beats.
    ########################################################

    minimum_scene_gap = 1
    maximum_jump_seconds = 70.0

    for beat_index in range(
        1,
        beat_count,
    ):

        beats_remaining = (
            beat_count
            - beat_index
            - 1
        )

        for current in range(
            scene_count
        ):

            # Reserve enough scenes after this one.
            scenes_after = (
                scene_count
                - current
                - 1
            )

            if scenes_after < beats_remaining:
                continue

            best_score = negative
            best_parent = -1

            for previous in range(
                0,
                current - minimum_scene_gap + 1,
            ):

                previous_score = dp[
                    beat_index - 1,
                    previous,
                ]

                if previous_score <= negative / 2:
                    continue

                delta = (
                    entries[
                        current
                    ][
                        "center"
                    ]
                    - entries[
                        previous
                    ][
                        "center"
                    ]
                )

                if delta <= 0:
                    continue

                ################################################
                # Penalize giant jumps so V4 doesn't leap
                # from 315 sec to 568 sec in only a few beats.
                ################################################

                jump_penalty = 0.0

                if delta > maximum_jump_seconds:
                    jump_penalty = (
                        delta
                        - maximum_jump_seconds
                    ) / 250.0

                ################################################
                # Duplicate-scene penalty.
                ################################################

                visual_similarity = float(
                    (
                        scene_features[
                            current
                        ]
                        @ scene_features[
                            previous
                        ]
                    ).item()
                )

                duplicate_penalty = 0.0

                if visual_similarity > 0.965:
                    duplicate_penalty = 0.20

                elif visual_similarity > 0.93:
                    duplicate_penalty = 0.08

                candidate_score = (
                    previous_score
                    + scores[
                        beat_index,
                        current,
                    ]
                    - jump_penalty
                    - duplicate_penalty
                )

                if candidate_score > best_score:

                    best_score = (
                        candidate_score
                    )

                    best_parent = (
                        previous
                    )

            if best_parent >= 0:

                dp[
                    beat_index,
                    current,
                ] = best_score

                parent[
                    beat_index,
                    current,
                ] = best_parent

    ########################################################
    # Recover best complete 22-shot sequence.
    ########################################################

    final_scene = int(
        np.argmax(
            dp[
                beat_count - 1
            ]
        )
    )

    if (
        dp[
            beat_count - 1,
            final_scene,
        ]
        <= negative / 2
    ):
        raise RuntimeError(
            "Global narrative planner could not "
            "build a complete sequence."
        )

    selected = [
        final_scene
    ]

    current = final_scene

    for beat_index in range(
        beat_count - 1,
        0,
        -1,
    ):

        current = int(
            parent[
                beat_index,
                current,
            ]
        )

        if current < 0:
            raise RuntimeError(
                "Broken global narrative path."
            )

        selected.append(
            current
        )

    selected.reverse()

    ########################################################
    # Print complete plan.
    ########################################################

    print()
    print(
        "========== NARRATIVE SHOT PLAN =========="
    )

    previous_time = None

    for beat_index, scene_index in enumerate(
        selected
    ):

        entry = entries[
            scene_index
        ]

        semantic = float(
            similarity[
                beat_index,
                scene_index,
            ]
        )

        if previous_time is None:
            jump = 0.0
        else:
            jump = (
                entry[
                    "center"
                ]
                - previous_time
            )

        previous_time = entry[
            "center"
        ]

        print(
            f"{beat_index + 1:02d}",
            "|",
            round(
                entry[
                    "center"
                ],
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
                float(
                    entry[
                        "quality"
                    ]
                ),
                3,
            ),
            "| JUMP:",
            round(
                jump,
                1,
            ),
            "|",
            VISUAL_BEATS[
                beat_index
            ],
        )

    return selected



def motion_score(
    source,
    timestamp: float,
    window: float = 0.22,
) -> float:
    """
    Approximate local motion using grayscale frame difference.
    """

    left = max(
        0.0,
        timestamp - window,
    )

    right = min(
        source.duration - 0.01,
        timestamp + window,
    )

    frame_a = source.get_frame(
        left
    ).astype(
        np.uint8
    )

    frame_b = source.get_frame(
        right
    ).astype(
        np.uint8
    )

    gray_a = cv2.cvtColor(
        frame_a,
        cv2.COLOR_RGB2GRAY,
    )

    gray_b = cv2.cvtColor(
        frame_b,
        cv2.COLOR_RGB2GRAY,
    )

    difference = cv2.absdiff(
        gray_a,
        gray_b,
    )

    raw = float(
        difference.mean()
    )

    return min(
        raw / 35.0,
        1.0,
    )


def composition_score(
    frame,
) -> tuple[float, float]:
    """
    Return:
        composition quality 0..1
        preferred horizontal focus ratio
    """

    focus = focus_x(
        frame
    )

    faces = detect_faces(
        frame
    )

    score = 0.72

    if faces:

        h, w = frame.shape[:2]

        centers = []

        total_area = 0.0

        for x, y, fw, fh in faces:

            centers.append(
                (
                    x + fw / 2
                )
                / w
            )

            total_area += (
                fw * fh
            ) / (
                w * h
            )

        group_center = float(
            np.mean(
                centers
            )
        )

        focus = group_center

        if (
            0.16
            <= group_center
            <= 0.84
        ):
            score += 0.14

        if (
            0.01
            <= total_area
            <= 0.35
        ):
            score += 0.12

    else:

        if (
            0.20
            <= focus
            <= 0.80
        ):
            score += 0.08

    return (
        min(
            score,
            1.0,
        ),
        max(
            0.12,
            min(
                0.88,
                float(focus),
            ),
        ),
    )


def local_scene_candidates(
    source,
    entry,
    *,
    beat_prompt: str,
    model,
    preprocess,
    tokenizer,
    device,
    desired_energy: float,
):
    """
    Search multiple moments INSIDE a selected scene.

    V4 always used scene center.
    V5 chooses the best cinematic moment within the scene.
    """

    start = float(
        entry["start"]
    )

    end = float(
        entry["end"]
    )

    duration = (
        end - start
    )

    if duration <= 0:
        return []

    margins = min(
        0.35,
        duration * 0.12,
    )

    sample_start = (
        start + margins
    )

    sample_end = (
        end - margins
    )

    if sample_end <= sample_start:

        sample_start = start
        sample_end = end

    timestamps = np.linspace(
        sample_start,
        sample_end,
        LOCAL_SAMPLE_COUNT,
    )

    text_tokens = tokenizer(
        [
            beat_prompt,
        ]
    ).to(
        device
    )

    with torch.no_grad():

        text_feature = normalize(
            model.encode_text(
                text_tokens
            )
        ).cpu()

    candidates = []

    for timestamp in timestamps:

        timestamp = float(
            timestamp
        )

        frame = source.get_frame(
            timestamp
        ).astype(
            np.uint8
        )

        quality = quality_score(
            frame
        )

        if quality is None:
            continue

        tensor = (
            preprocess(
                Image.fromarray(
                    frame
                ).convert(
                    "RGB"
                )
            )
            .unsqueeze(0)
            .to(
                device
            )
        )

        with torch.no_grad():

            image_feature = normalize(
                model.encode_image(
                    tensor
                )
            ).cpu()

        semantic = float(
            (
                text_feature
                @ image_feature.T
            ).item()
        )

        motion = motion_score(
            source,
            timestamp,
        )

        composition, focus = (
            composition_score(
                frame
            )
        )

        ####################################################
        # Match shot intensity to narrative energy curve.
        ####################################################

        energy_match = max(
            0.0,
            1.0
            - abs(
                motion
                - desired_energy
            ),
        )

        local_score = (
            semantic * 0.44
            + float(
                quality
            ) * 0.20
            + composition * 0.18
            + energy_match * 0.18
        )

        if (
            semantic
            < MIN_LOCAL_SEMANTIC
        ):
            local_score -= (
                MIN_LOCAL_SEMANTIC
                - semantic
            ) * 1.4

        candidates.append(
            {
                "timestamp": timestamp,
                "semantic": semantic,
                "quality": float(
                    quality
                ),
                "motion": motion,
                "composition": composition,
                "focus_x": focus,
                "energy_match": energy_match,
                "score": float(
                    local_score
                ),
                "embedding": (
                    image_feature[
                        0
                    ]
                ),
            }
        )

    candidates.sort(
        key=lambda item: (
            item[
                "score"
            ]
        ),
        reverse=True,
    )

    return candidates


def optimize_selected_moments(
    source,
    entries,
    selected,
    *,
    model,
    preprocess,
    tokenizer,
    device,
):
    """
    Second-stage shot optimizer.

    Scene selection chooses WHAT scene.
    This chooses WHICH exact moment inside that scene.
    """

    print()
    print(
        "========== V5 LOCAL SHOT OPTIMIZER =========="
    )

    output = []

    recent_embeddings = []

    for beat_index, scene_index in enumerate(
        selected
    ):

        entry = entries[
            scene_index
        ]

        candidates = (
            local_scene_candidates(
                source,
                entry,
                beat_prompt=(
                    VISUAL_BEATS[
                        beat_index
                    ]
                ),
                model=model,
                preprocess=preprocess,
                tokenizer=tokenizer,
                device=device,
                desired_energy=(
                    ENERGY_CURVE[
                        beat_index
                    ]
                ),
            )
        )

        winner = None

        for candidate in candidates:

            if (
                candidate[
                    "quality"
                ]
                < MIN_LOCAL_QUALITY
            ):
                continue

            duplicate = False

            for prior in (
                recent_embeddings[
                    -4:
                ]
            ):

                similarity = float(
                    (
                        candidate[
                            "embedding"
                        ]
                        @ prior
                    ).item()
                )

                if (
                    similarity
                    >= MAX_NEAR_DUPLICATE
                ):

                    duplicate = True
                    break

            if duplicate:
                continue

            winner = candidate
            break

        if winner is None:

            if not candidates:
                raise RuntimeError(
                    "No usable local candidates "
                    f"for beat {beat_index + 1}."
                )

            winner = candidates[
                0
            ]

        output.append(
            winner
        )

        recent_embeddings.append(
            winner[
                "embedding"
            ]
        )

        print(
            f"{beat_index + 1:02d}",
            "|",
            round(
                winner[
                    "timestamp"
                ],
                2,
            ),
            "sec",
            "| SEM:",
            round(
                winner[
                    "semantic"
                ],
                4,
            ),
            "| MOT:",
            round(
                winner[
                    "motion"
                ],
                3,
            ),
            "| COMP:",
            round(
                winner[
                    "composition"
                ],
                3,
            ),
            "| ENERGY:",
            round(
                winner[
                    "energy_match"
                ],
                3,
            ),
            "|",
            VISUAL_BEATS[
                beat_index
            ],
        )

    return output


def narration_caption_chunks():
    """
    Split narration into readable 2-4 word phrases.
    """

    words = (
        NARRATION
        .replace(
            ",",
            "",
        )
        .replace(
            ".",
            "",
        )
        .replace(
            ":",
            "",
        )
        .split()
    )

    chunks = []

    index = 0

    pattern = (
        3,
        3,
        4,
        3,
    )

    pattern_index = 0

    while index < len(words):

        size = pattern[
            pattern_index
            % len(
                pattern
            )
        ]

        chunk = words[
            index:
            index + size
        ]

        if not chunk:
            break

        chunks.append(
            " ".join(
                chunk
            ).upper()
        )

        index += size
        pattern_index += 1

    return chunks


def build_synced_captions(
    voice_duration: float,
):
    """
    Approximate phrase timing proportional to narration length.

    Better than V4's six fixed caption cards.
    """

    chunks = (
        narration_caption_chunks()
    )

    if not chunks:
        return []

    total_words = sum(
        len(
            chunk.split()
        )
        for chunk in chunks
    )

    usable_duration = min(
        voice_duration,
        TARGET_DURATION,
    )

    current = 0.0

    schedule = []

    for chunk in chunks:

        words = len(
            chunk.split()
        )

        duration = (
            usable_duration
            * words
            / max(
                total_words,
                1,
            )
        )

        duration = max(
            0.45,
            duration,
        )

        end = min(
            usable_duration,
            current + duration,
        )

        schedule.append(
            (
                current,
                end,
                chunk,
            )
        )

        current = end

        if current >= usable_duration:
            break

    return schedule




############################################################
# V8 â€” WHOLE-SHOT QUALITY
############################################################

def whole_shot_quality_v8(
    source,
    *,
    timestamp,
    scene_start,
    scene_end,
    duration,
):
    start = max(
        scene_start,
        timestamp - duration / 2,
    )

    if start + duration > scene_end:
        start = max(
            scene_start,
            scene_end - duration,
        )

    end = min(
        scene_end,
        start + duration,
    )

    if end - start < duration * 0.60:
        return 0.0

    sample_times = np.linspace(
        start,
        end,
        7,
    )

    scores = []

    for t in sample_times:

        frame = source.get_frame(
            float(t)
        ).astype(
            np.uint8
        )

        q = quality_score(frame)

        if q is None:
            scores.append(0.0)
            continue

        comp, _ = composition_score(
            frame
        )

        scores.append(
            float(q) * 0.62
            + float(comp) * 0.38
        )

    if not scores:
        return 0.0

    # Penalize a shot containing even a few terrible frames.
    average = float(
        np.mean(scores)
    )

    low = float(
        np.percentile(
            scores,
            20,
        )
    )

    return (
        average * 0.72
        + low * 0.28
    )


############################################################
# V8 â€” CANDIDATE POOLS
############################################################

def build_candidate_pools_v8(
    source,
    entries,
    selected,
    *,
    model,
    preprocess,
    tokenizer,
    device,
):
    print()
    print(
        "========== V8 CANDIDATE POOLS =========="
    )

    pools = []

    for beat_index, scene_index in enumerate(
        selected
    ):

        entry = entries[
            scene_index
        ]

        candidates = local_scene_candidates(
            source,
            entry,
            beat_prompt=(
                VISUAL_BEATS[
                    beat_index
                ]
            ),
            model=model,
            preprocess=preprocess,
            tokenizer=tokenizer,
            device=device,
            desired_energy=(
                ENERGY_CURVE[
                    beat_index
                ]
            ),
        )

        enhanced = []

        for candidate in candidates:

            whole_quality = (
                whole_shot_quality_v8(
                    source,
                    timestamp=float(
                        candidate[
                            "timestamp"
                        ]
                    ),
                    scene_start=float(
                        entry[
                            "start"
                        ]
                    ),
                    scene_end=float(
                        entry[
                            "end"
                        ]
                    ),
                    duration=float(
                        SHOT_DURATIONS[
                            beat_index
                        ]
                    ),
                )
            )

            if whole_quality < 0.36:
                continue

            candidate = dict(
                candidate
            )

            candidate[
                "whole_quality"
            ] = whole_quality

            candidate[
                "intrinsic"
            ] = (
                candidate[
                    "semantic"
                ] * 0.38
                + candidate[
                    "quality"
                ] * 0.17
                + candidate[
                    "composition"
                ] * 0.15
                + candidate[
                    "energy_match"
                ] * 0.12
                + whole_quality * 0.18
            )

            enhanced.append(
                candidate
            )

        enhanced.sort(
            key=lambda x: x[
                "intrinsic"
            ],
            reverse=True,
        )

        # Keep only the strongest alternatives.
        pool = enhanced[:7]

        if not pool:

            # Fail soft rather than killing the render.
            fallback = dict(
                candidates[0]
            )

            fallback[
                "whole_quality"
            ] = 0.30

            fallback[
                "intrinsic"
            ] = fallback[
                "score"
            ]

            pool = [
                fallback
            ]

        pools.append(
            pool
        )

        print(
            f"{beat_index + 1:02d}",
            "| candidates:",
            len(pool),
            "| best:",
            round(
                float(
                    pool[0][
                        "intrinsic"
                    ]
                ),
                4,
            ),
            "|",
            VISUAL_BEATS[
                beat_index
            ],
        )

    return pools


############################################################
# V8 â€” GLOBAL EXACT-SHOT BEAM SEARCH
############################################################

def optimize_complete_sequence_v8(
    pools,
):
    """
    Optimize the entire 22-shot sequence jointly.

    This is the key V8 change.

    V5/V6:
        choose best exact moment independently.

    V8:
        evaluate transition quality between shots.
    """

    print()
    print(
        "========== V8 GLOBAL SHOT OPTIMIZER =========="
    )

    BEAM_WIDTH = 80

    # State:
    # (
    #   total_score,
    #   chosen_candidates,
    # )

    beam = []

    for candidate in pools[0]:

        hook_bonus = (
            candidate[
                "motion"
            ] * 0.10
            + candidate[
                "composition"
            ] * 0.08
            + candidate[
                "semantic"
            ] * 0.06
        )

        beam.append(
            (
                candidate[
                    "intrinsic"
                ]
                + hook_bonus,
                [
                    candidate
                ],
            )
        )

    beam.sort(
        key=lambda x: x[0],
        reverse=True,
    )

    beam = beam[
        :BEAM_WIDTH
    ]

    for beat_index in range(
        1,
        len(pools),
    ):

        next_beam = []

        for total_score, sequence in beam:

            previous = sequence[
                -1
            ]

            previous_embeddings = [
                item[
                    "embedding"
                ]
                for item
                in sequence
            ]

            for candidate in pools[
                beat_index
            ]:

                ################################################
                # Duplicate control against ALL selected shots.
                ################################################

                similarities = [
                    float(
                        (
                            candidate[
                                "embedding"
                            ]
                            @ embedding
                        ).item()
                    )
                    for embedding
                    in previous_embeddings
                ]

                max_similarity = max(
                    similarities
                )

                if max_similarity >= 0.975:
                    continue

                duplicate_penalty = 0.0

                if max_similarity > 0.94:
                    duplicate_penalty += (
                        max_similarity - 0.94
                    ) * 2.6

                ################################################
                # Adjacent-shot transition.
                ################################################

                adjacent_similarity = float(
                    (
                        candidate[
                            "embedding"
                        ]
                        @ previous[
                            "embedding"
                        ]
                    ).item()
                )

                # Too similar = repetitive cut.
                similarity_penalty = 0.0

                if adjacent_similarity > 0.91:
                    similarity_penalty = (
                        adjacent_similarity
                        - 0.91
                    ) * 1.8

                ################################################
                # Motion progression.
                ################################################

                desired_change = (
                    ENERGY_CURVE[
                        beat_index
                    ]
                    - ENERGY_CURVE[
                        beat_index - 1
                    ]
                )

                actual_change = (
                    candidate[
                        "motion"
                    ]
                    - previous[
                        "motion"
                    ]
                )

                energy_transition = max(
                    0.0,
                    1.0
                    - abs(
                        desired_change
                        - actual_change
                    ),
                )

                ################################################
                # Prevent violent crop jumping between shots.
                ################################################

                focus_jump = abs(
                    candidate[
                        "focus_x"
                    ]
                    - previous[
                        "focus_x"
                    ]
                )

                focus_penalty = max(
                    0.0,
                    focus_jump - 0.34,
                ) * 0.20

                ################################################
                # Reward visual change without total randomness.
                ################################################

                novelty = max(
                    0.0,
                    1.0
                    - adjacent_similarity,
                )

                transition_score = (
                    energy_transition * 0.08
                    + novelty * 0.045
                    - similarity_penalty
                    - duplicate_penalty
                    - focus_penalty
                )

                score = (
                    total_score
                    + candidate[
                        "intrinsic"
                    ]
                    + transition_score
                )

                next_beam.append(
                    (
                        score,
                        sequence
                        + [
                            candidate
                        ],
                    )
                )

        if not next_beam:

            raise RuntimeError(
                "V8 beam search exhausted at beat "
                f"{beat_index + 1}."
            )

        next_beam.sort(
            key=lambda x: x[0],
            reverse=True,
        )

        beam = next_beam[
            :BEAM_WIDTH
        ]

    best_score, best_sequence = (
        beam[0]
    )

    print(
        "GLOBAL SCORE:",
        round(
            float(best_score),
            4,
        ),
    )

    for index, candidate in enumerate(
        best_sequence,
        start=1,
    ):

        print(
            f"{index:02d}",
            "|",
            round(
                candidate[
                    "timestamp"
                ],
                2,
            ),
            "sec",
            "| SEM:",
            round(
                candidate[
                    "semantic"
                ],
                4,
            ),
            "| WHOLE:",
            round(
                candidate[
                    "whole_quality"
                ],
                3,
            ),
            "| MOT:",
            round(
                candidate[
                    "motion"
                ],
                3,
            ),
        )

    return best_sequence


############################################################
# V8 â€” DYNAMIC SUBJECT TRACK
############################################################

def build_focus_track_v8(
    source,
    *,
    start,
    end,
):
    times = np.linspace(
        start,
        end,
        11,
    )

    focus_values = []

    for timestamp in times:

        frame = source.get_frame(
            float(timestamp)
        ).astype(
            np.uint8
        )

        _, focus = composition_score(
            frame
        )

        focus_values.append(
            float(
                focus
            )
        )

    ########################################################
    # Smooth heavily to stop robotic camera hunting.
    ########################################################

    smoothed = []

    for index in range(
        len(focus_values)
    ):

        left = max(
            0,
            index - 2,
        )

        right = min(
            len(focus_values),
            index + 3,
        )

        smoothed.append(
            float(
                np.median(
                    focus_values[
                        left:right
                    ]
                )
            )
        )

    stable = [
        smoothed[0]
    ]

    DEAD_ZONE = 0.035
    MAX_STEP = 0.055

    for target in smoothed[
        1:
    ]:

        current = stable[
            -1
        ]

        delta = (
            target - current
        )

        if abs(delta) < DEAD_ZONE:

            stable.append(
                current
            )

            continue

        delta = max(
            -MAX_STEP,
            min(
                MAX_STEP,
                delta,
            ),
        )

        stable.append(
            current + delta
        )

    return [
        (
            float(
                t - start
            ),
            max(
                0.12,
                min(
                    0.88,
                    value,
                ),
            ),
        )
        for t, value
        in zip(
            times,
            stable,
        )
    ]


def dynamic_crop_v8(
    clip,
    focus_track,
):
    track_t = np.array(
        [
            item[0]
            for item
            in focus_track
        ],
        dtype=np.float32,
    )

    track_x = np.array(
        [
            item[1]
            for item
            in focus_track
        ],
        dtype=np.float32,
    )

    def transform(
        get_frame,
        t,
    ):

        frame = np.asarray(
            get_frame(t)
        ).astype(
            np.uint8
        )

        h, w = frame.shape[
            :2
        ]

        scale = max(
            WIDTH / w,
            HEIGHT / h,
        )

        rw = int(
            np.ceil(
                w * scale
            )
        )

        rh = int(
            np.ceil(
                h * scale
            )
        )

        resized = cv2.resize(
            frame,
            (
                rw,
                rh,
            ),
            interpolation=(
                cv2.INTER_LANCZOS4
            ),
        )

        focus = float(
            np.interp(
                float(t),
                track_t,
                track_x,
            )
        )

        cx = (
            rw * focus
        )

        half = (
            WIDTH / 2
        )

        cx = max(
            half,
            min(
                rw - half,
                cx,
            ),
        )

        x1 = int(
            round(
                cx - half
            )
        )

        x1 = max(
            0,
            min(
                rw - WIDTH,
                x1,
            ),
        )

        y1 = max(
            0,
            int(
                (
                    rh - HEIGHT
                )
                / 2
            ),
        )

        output = resized[
            y1:y1 + HEIGHT,
            x1:x1 + WIDTH,
        ]

        if (
            output.shape[0]
            != HEIGHT
            or output.shape[1]
            != WIDTH
        ):

            output = cv2.resize(
                output,
                (
                    WIDTH,
                    HEIGHT,
                ),
                interpolation=(
                    cv2.INTER_LANCZOS4
                ),
            )

        return output

    return clip.transform(
        transform
    )


############################################################
# V8 â€” CLEANER CAPTIONS
############################################################

def caption_chunks_v8():

    import re

    words = re.sub(
        r"[^\w\s']",
        " ",
        NARRATION,
    ).split()

    groups = []

    pattern = (
        3,
        3,
        2,
        3,
    )

    cursor = 0
    pattern_index = 0

    while cursor < len(words):

        size = pattern[
            pattern_index
            % len(pattern)
        ]

        group = words[
            cursor:
            cursor + size
        ]

        if not group:
            break

        groups.append(
            " ".join(
                group
            ).upper()
        )

        cursor += size

        pattern_index += 1

    return groups


def caption_schedule_v8(
    voice_duration,
):
    chunks = caption_chunks_v8()

    if not chunks:
        return []

    weights = [
        sum(
            max(
                1.0,
                len(word) / 4.6,
            )
            for word
            in chunk.split()
        )
        for chunk
        in chunks
    ]

    total = sum(
        weights
    )

    usable = min(
        float(
            voice_duration
        ),
        TARGET_DURATION,
    )

    position = 0.0

    schedule = []

    for chunk, weight in zip(
        chunks,
        weights,
    ):

        duration = (
            usable
            * weight
            / total
        )

        duration = max(
            0.42,
            min(
                1.15,
                duration,
            ),
        )

        end = min(
            usable,
            position + duration,
        )

        schedule.append(
            (
                position,
                end,
                chunk,
            )
        )

        position = end

        if position >= usable:
            break

    return schedule


############################################################
# V8 â€” FINAL QA
############################################################

def final_qa_v8(
    moments,
):
    semantic = np.array(
        [
            item[
                "semantic"
            ]
            for item
            in moments
        ],
        dtype=np.float32,
    )

    quality = np.array(
        [
            item[
                "whole_quality"
            ]
            for item
            in moments
        ],
        dtype=np.float32,
    )

    print()
    print(
        "========== V8 FINAL QA =========="
    )

    print(
        "AVG SEMANTIC:",
        round(
            float(
                semantic.mean()
            ),
            4,
        ),
    )

    print(
        "MIN SEMANTIC:",
        round(
            float(
                semantic.min()
            ),
            4,
        ),
    )

    print(
        "AVG WHOLE-SHOT QUALITY:",
        round(
            float(
                quality.mean()
            ),
            4,
        ),
    )

    weak = int(
        (
            semantic < 0.145
        ).sum()
    )

    poor = int(
        (
            quality < 0.40
        ).sum()
    )

    print(
        "WEAK SEMANTIC:",
        weak,
    )

    print(
        "POOR SHOTS:",
        poor,
    )

    if weak > 3:
        raise RuntimeError(
            "V8 rejected: too many weak semantic shots."
        )

    if poor > 2:
        raise RuntimeError(
            "V8 rejected: too many poor visual shots."
        )




############################################################
# V9 â€” EDITORIAL ROLE DEFINITIONS
############################################################

FACE_BEATS = {
    2,
    3,
    4,
    8,
    9,
    10,
    14,
    15,
    19,
}

ACTION_BEATS = {
    16,
    17,
    18,
    20,
    21,
}


def encode_text_v9(
    texts,
    *,
    model,
    tokenizer,
    device,
):

    tokens = tokenizer(
        texts
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


def build_editorial_features_v9(
    *,
    model,
    tokenizer,
    device,
):

    prompts = [
        # 0
        (
            "clear visible human face "
            "cinematic reaction close up"
        ),

        # 1
        (
            "object machinery scenery "
            "without a visible human face"
        ),

        # 2
        (
            "dynamic cinematic action "
            "movement danger dramatic motion"
        ),

        # 3
        (
            "static quiet object still frame "
            "without action"
        ),

        # 4
        (
            "visually striking dramatic movie hook "
            "cinematic suspense action or reaction"
        ),

        # 5
        (
            "ordinary transitional background shot "
            "unimportant visual"
        ),

        # 6
        (
            "cinematic climax powerful final shot "
            "dramatic action reaction danger"
        ),

        # 7
        (
            "weak quiet transitional ending "
            "flat unimportant shot"
        ),
    ]

    return encode_text_v9(
        prompts,
        model=model,
        tokenizer=tokenizer,
        device=device,
    )


############################################################
# V9 â€” HARD WHOLE-SHOT HEALTH
############################################################

def segment_health_v9(
    source,
    *,
    timestamp,
    scene_start,
    scene_end,
    duration,
):
    """
    A human editor would reject a clip if several frames are:

      - blown out
      - crushed black
      - extremely soft
      - almost textureless

    V9 makes those hard editorial failures.
    """

    start = max(
        float(scene_start),
        float(timestamp)
        - float(duration) / 2,
    )

    if (
        start + duration
        > scene_end
    ):

        start = max(
            float(scene_start),
            float(scene_end)
            - float(duration),
        )

    end = min(
        float(scene_end),
        start + float(duration),
    )

    if end <= start:

        return {
            "valid": False,
            "score": 0.0,
            "blown": 1.0,
            "crushed": 1.0,
        }

    sample_times = np.linspace(
        start,
        end,
        9,
    )

    quality_values = []

    blown_values = []
    crushed_values = []

    bad_frames = 0

    for sample_time in sample_times:

        frame = source.get_frame(
            float(sample_time)
        ).astype(
            np.uint8
        )

        gray = cv2.cvtColor(
            frame,
            cv2.COLOR_RGB2GRAY,
        )

        blown = float(
            (
                gray >= 248
            ).mean()
        )

        crushed = float(
            (
                gray <= 7
            ).mean()
        )

        blown_values.append(
            blown
        )

        crushed_values.append(
            crushed
        )

        q = quality_score(
            frame
        )

        if q is None:

            bad_frames += 1
            quality_values.append(
                0.0
            )

        else:

            quality_values.append(
                float(q)
            )

        if blown > 0.24:

            bad_frames += 1

        if crushed > 0.58:

            bad_frames += 1

    average_quality = float(
        np.mean(
            quality_values
        )
    )

    low_quality = float(
        np.percentile(
            quality_values,
            20,
        )
    )

    average_blown = float(
        np.mean(
            blown_values
        )
    )

    average_crushed = float(
        np.mean(
            crushed_values
        )
    )

    bad_ratio = (
        bad_frames
        / max(
            len(sample_times),
            1,
        )
    )

    score = (
        average_quality * 0.72
        + low_quality * 0.28
    )

    score -= (
        average_blown * 0.55
    )

    score -= (
        average_crushed * 0.25
    )

    valid = (
        bad_ratio <= 0.33
        and average_blown < 0.16
        and score >= 0.38
    )

    return {
        "valid": bool(valid),
        "score": float(
            max(
                0.0,
                score,
            )
        ),
        "blown": average_blown,
        "crushed": average_crushed,
        "bad_ratio": bad_ratio,
    }


############################################################
# V9 â€” ROLE SCORES
############################################################

def editorial_role_scores_v9(
    candidate,
    features,
):

    embedding = candidate[
        "embedding"
    ]

    values = [
        float(
            (
                embedding
                @ features[
                    index
                ]
            ).item()
        )
        for index
        in range(
            len(features)
        )
    ]

    face_margin = (
        values[0]
        - values[1]
    )

    action_margin = (
        values[2]
        - values[3]
    )

    hook_margin = (
        values[4]
        - values[5]
    )

    ending_margin = (
        values[6]
        - values[7]
    )

    return {
        "face_margin": (
            face_margin
        ),
        "action_margin": (
            action_margin
        ),
        "hook_margin": (
            hook_margin
        ),
        "ending_margin": (
            ending_margin
        ),
    }


############################################################
# V9 â€” SPECIAL GLOBAL HOOK / END SEARCH
############################################################

def global_extreme_candidates_v9(
    source,
    entries,
    scene_features,
    *,
    beat_index,
    model,
    preprocess,
    tokenizer,
    device,
    editorial_features,
):
    """
    Beat 1 and beat 22 are allowed to search much more broadly
    than normal beats.

    Hook and ending quality outrank strict chronology.
    """

    if beat_index == 0:

        special_prompt = (
            "visually striking dramatic science fiction "
            "movie hook suspense action face reaction"
        )

        lower = SEARCH_START
        upper = min(
            SEARCH_START + 230.0,
            SEARCH_END,
        )

    elif beat_index == (
        len(VISUAL_BEATS) - 1
    ):

        special_prompt = (
            "powerful cinematic science fiction climax "
            "dramatic final action reaction shot"
        )

        lower = max(
            SEARCH_START,
            SEARCH_END - 260.0,
        )

        upper = SEARCH_END

    else:

        return []

    text_feature = encode_text_v9(
        [
            special_prompt,
        ],
        model=model,
        tokenizer=tokenizer,
        device=device,
    )[0]

    ranked_scenes = []

    for scene_index, entry in enumerate(
        entries
    ):

        center = float(
            entry[
                "center"
            ]
        )

        if not (
            lower
            <= center
            <= upper
        ):

            continue

        score = float(
            (
                scene_features[
                    scene_index
                ]
                @ text_feature
            ).item()
        )

        ranked_scenes.append(
            (
                score,
                scene_index,
            )
        )

    ranked_scenes.sort(
        reverse=True
    )

    output = []

    for _, scene_index in (
        ranked_scenes[
            :12
        ]
    ):

        entry = entries[
            scene_index
        ]

        candidates = (
            local_scene_candidates(
                source,
                entry,
                beat_prompt=(
                    VISUAL_BEATS[
                        beat_index
                    ]
                    + " "
                    + special_prompt
                ),
                model=model,
                preprocess=preprocess,
                tokenizer=tokenizer,
                device=device,
                desired_energy=(
                    ENERGY_CURVE[
                        beat_index
                    ]
                ),
            )
        )

        for candidate in candidates[
            :4
        ]:

            health = (
                segment_health_v9(
                    source,
                    timestamp=(
                        candidate[
                            "timestamp"
                        ]
                    ),
                    scene_start=(
                        entry[
                            "start"
                        ]
                    ),
                    scene_end=(
                        entry[
                            "end"
                        ]
                    ),
                    duration=(
                        SHOT_DURATIONS[
                            beat_index
                        ]
                    ),
                )
            )

            if not health[
                "valid"
            ]:

                continue

            role = (
                editorial_role_scores_v9(
                    candidate,
                    editorial_features,
                )
            )

            candidate = dict(
                candidate
            )

            candidate[
                "whole_quality"
            ] = health[
                "score"
            ]

            candidate[
                "scene_index_v9"
            ] = scene_index

            candidate.update(
                role
            )

            if beat_index == 0:

                special_score = (
                    role[
                        "hook_margin"
                    ]
                )

            else:

                special_score = (
                    role[
                        "ending_margin"
                    ]
                )

            candidate[
                "intrinsic"
            ] = (
                candidate[
                    "semantic"
                ] * 0.30
                + candidate[
                    "quality"
                ] * 0.14
                + candidate[
                    "composition"
                ] * 0.18
                + candidate[
                    "motion"
                ] * 0.12
                + health[
                    "score"
                ] * 0.18
                + special_score * 0.08
            )

            output.append(
                candidate
            )

    output.sort(
        key=lambda item: (
            item[
                "intrinsic"
            ]
        ),
        reverse=True,
    )

    return output[
        :10
    ]


############################################################
# V9 â€” HUMAN EDITOR GATE
############################################################

def upgrade_candidate_pools_v9(
    source,
    entries,
    selected,
    pools,
    scene_features,
    *,
    model,
    preprocess,
    tokenizer,
    device,
):
    """
    Turn V8's mathematically-good candidates into candidates
    a human editor would actually consider using.
    """

    print()
    print(
        "========== V9 HUMAN EDITOR GATE =========="
    )

    editorial_features = (
        build_editorial_features_v9(
            model=model,
            tokenizer=tokenizer,
            device=device,
        )
    )

    upgraded = []

    for beat_index, pool in enumerate(
        pools
    ):

        scene_index = selected[
            beat_index
        ]

        entry = entries[
            scene_index
        ]

        working = list(
            pool
        )

        ####################################################
        # Expand hook / ending beyond original scene.
        ####################################################

        if (
            beat_index == 0
            or beat_index
            == len(
                VISUAL_BEATS
            ) - 1
        ):

            working.extend(
                global_extreme_candidates_v9(
                    source,
                    entries,
                    scene_features,
                    beat_index=(
                        beat_index
                    ),
                    model=model,
                    preprocess=preprocess,
                    tokenizer=tokenizer,
                    device=device,
                    editorial_features=(
                        editorial_features
                    ),
                )
            )

        accepted = []

        seen_times = []

        rejected = 0

        for candidate in working:

            timestamp = float(
                candidate[
                    "timestamp"
                ]
            )

            if any(
                abs(
                    timestamp - old
                )
                < 0.65
                for old
                in seen_times
            ):

                continue

            ################################################
            # If special global candidate stores its own scene.
            ################################################

            candidate_scene_index = int(
                candidate.get(
                    "scene_index_v9",
                    scene_index,
                )
            )

            candidate_entry = entries[
                candidate_scene_index
            ]

            health = (
                segment_health_v9(
                    source,
                    timestamp=timestamp,
                    scene_start=(
                        candidate_entry[
                            "start"
                        ]
                    ),
                    scene_end=(
                        candidate_entry[
                            "end"
                        ]
                    ),
                    duration=(
                        SHOT_DURATIONS[
                            beat_index
                        ]
                    ),
                )
            )

            if not health[
                "valid"
            ]:

                rejected += 1
                continue

            role = (
                editorial_role_scores_v9(
                    candidate,
                    editorial_features,
                )
            )

            ################################################
            # FACE / REACTION beats.
            ################################################

            if beat_index in FACE_BEATS:

                # CLIP must not think this looks more like
                # machinery/scenery than a visible face.
                if (
                    role[
                        "face_margin"
                    ]
                    < -0.025
                ):

                    rejected += 1
                    continue

            ################################################
            # ACTION beats.
            ################################################

            if beat_index in ACTION_BEATS:

                if (
                    candidate[
                        "motion"
                    ] < 0.10
                    and role[
                        "action_margin"
                    ] < 0.015
                ):

                    rejected += 1
                    continue

            candidate = dict(
                candidate
            )

            candidate.update(
                role
            )

            candidate[
                "whole_quality"
            ] = (
                health[
                    "score"
                ]
            )

            candidate[
                "scene_index_v9"
            ] = (
                candidate_scene_index
            )

            role_bonus = 0.0

            if beat_index in FACE_BEATS:

                role_bonus += (
                    role[
                        "face_margin"
                    ]
                    * 0.10
                )

            if beat_index in ACTION_BEATS:

                role_bonus += (
                    role[
                        "action_margin"
                    ]
                    * 0.10
                )

            if beat_index == 0:

                role_bonus += (
                    role[
                        "hook_margin"
                    ]
                    * 0.14
                )

            if (
                beat_index
                == len(
                    VISUAL_BEATS
                ) - 1
            ):

                role_bonus += (
                    role[
                        "ending_margin"
                    ]
                    * 0.16
                )

            candidate[
                "intrinsic"
            ] = (
                candidate.get(
                    "intrinsic",
                    candidate[
                        "score"
                    ],
                )
                * 0.72
                + health[
                    "score"
                ]
                * 0.20
                + role_bonus
            )

            accepted.append(
                candidate
            )

            seen_times.append(
                timestamp
            )

        accepted.sort(
            key=lambda item: (
                item[
                    "intrinsic"
                ]
            ),
            reverse=True,
        )

        if not accepted:

            ################################################
            # V9.1 EDITORIAL RECOVERY
            #
            # Do NOT weaken the normal gate.
            #
            # If the planned scene has no acceptable shot,
            # search neighboring scenes for a replacement
            # that still satisfies the narrative role.
            ################################################

            print(
                "EDITORIAL RECOVERY:",
                beat_index + 1,
                "|",
                VISUAL_BEATS[
                    beat_index
                ],
            )

            recovery = []

            original_scene_index = (
                scene_index
            )

            neighborhood = range(
                max(
                    0,
                    original_scene_index - 6,
                ),
                min(
                    len(entries),
                    original_scene_index + 7,
                ),
            )

            for recovery_scene_index in neighborhood:

                recovery_entry = entries[
                    recovery_scene_index
                ]

                recovery_candidates = (
                    local_scene_candidates(
                        source,
                        recovery_entry,
                        beat_prompt=(
                            VISUAL_BEATS[
                                beat_index
                            ]
                        ),
                        model=model,
                        preprocess=preprocess,
                        tokenizer=tokenizer,
                        device=device,
                        desired_energy=(
                            ENERGY_CURVE[
                                beat_index
                            ]
                        ),
                    )
                )

                for candidate in recovery_candidates:

                    timestamp = float(
                        candidate[
                            "timestamp"
                        ]
                    )

                    health = (
                        segment_health_v9(
                            source,
                            timestamp=timestamp,
                            scene_start=(
                                recovery_entry[
                                    "start"
                                ]
                            ),
                            scene_end=(
                                recovery_entry[
                                    "end"
                                ]
                            ),
                            duration=(
                                SHOT_DURATIONS[
                                    beat_index
                                ]
                            ),
                        )
                    )

                    if not health[
                        "valid"
                    ]:
                        continue

                    role = (
                        editorial_role_scores_v9(
                            candidate,
                            editorial_features,
                        )
                    )

                    ################################################
                    # Recovery thresholds remain stricter than V8,
                    # but slightly less rigid than V9's primary gate.
                    ################################################

                    if beat_index in FACE_BEATS:

                        if (
                            role[
                                "face_margin"
                            ]
                            < -0.075
                        ):
                            continue

                    if beat_index in ACTION_BEATS:

                        if (
                            candidate[
                                "motion"
                            ] < 0.075
                            and role[
                                "action_margin"
                            ] < -0.01
                        ):
                            continue

                    candidate = dict(
                        candidate
                    )

                    candidate.update(
                        role
                    )

                    candidate[
                        "whole_quality"
                    ] = health[
                        "score"
                    ]

                    candidate[
                        "scene_index_v9"
                    ] = (
                        recovery_scene_index
                    )

                    ################################################
                    # Prefer:
                    #  semantic relevance
                    #  whole-shot health
                    #  correct role
                    #  composition
                    ################################################

                    role_bonus = 0.0

                    if beat_index in FACE_BEATS:

                        role_bonus += max(
                            -0.03,
                            role[
                                "face_margin"
                            ],
                        ) * 0.14

                    if beat_index in ACTION_BEATS:

                        role_bonus += max(
                            -0.03,
                            role[
                                "action_margin"
                            ],
                        ) * 0.12

                    distance = abs(
                        recovery_scene_index
                        - original_scene_index
                    )

                    continuity_penalty = (
                        distance
                        * 0.006
                    )

                    candidate[
                        "intrinsic"
                    ] = (
                        candidate[
                            "semantic"
                        ] * 0.35
                        + candidate[
                            "quality"
                        ] * 0.15
                        + candidate[
                            "composition"
                        ] * 0.17
                        + health[
                            "score"
                        ] * 0.23
                        + role_bonus
                        - continuity_penalty
                    )

                    recovery.append(
                        candidate
                    )

            recovery.sort(
                key=lambda item: (
                    item[
                        "intrinsic"
                    ]
                ),
                reverse=True,
            )

            ################################################
            # If neighboring scenes still cannot satisfy the
            # role, use the strongest healthy original
            # candidate rather than accepting garbage.
            ################################################

            if recovery:

                accepted = recovery[
                    :8
                ]

                print(
                    "RECOVERY SUCCESS:",
                    beat_index + 1,
                    "| alternatives:",
                    len(
                        accepted
                    ),
                    "| best scene:",
                    accepted[
                        0
                    ][
                        "scene_index_v9"
                    ],
                    "| semantic:",
                    round(
                        float(
                            accepted[
                                0
                            ][
                                "semantic"
                            ]
                        ),
                        4,
                    ),
                    "| face:",
                    round(
                        float(
                            accepted[
                                0
                            ].get(
                                "face_margin",
                                0.0,
                            )
                        ),
                        4,
                    ),
                )

            else:

                ################################################
                # Last-resort healthy candidate.
                #
                # This is still quality-gated. It only relaxes
                # the role classifier, which can be imperfect.
                ################################################

                fallback = []

                for candidate in working:

                    candidate_scene_index = int(
                        candidate.get(
                            "scene_index_v9",
                            scene_index,
                        )
                    )

                    fallback_entry = entries[
                        candidate_scene_index
                    ]

                    health = (
                        segment_health_v9(
                            source,
                            timestamp=float(
                                candidate[
                                    "timestamp"
                                ]
                            ),
                            scene_start=float(
                                fallback_entry[
                                    "start"
                                ]
                            ),
                            scene_end=float(
                                fallback_entry[
                                    "end"
                                ]
                            ),
                            duration=float(
                                SHOT_DURATIONS[
                                    beat_index
                                ]
                            ),
                        )
                    )

                    if not health[
                        "valid"
                    ]:
                        continue

                    role = (
                        editorial_role_scores_v9(
                            candidate,
                            editorial_features,
                        )
                    )

                    candidate = dict(
                        candidate
                    )

                    candidate.update(
                        role
                    )

                    candidate[
                        "whole_quality"
                    ] = health[
                        "score"
                    ]

                    candidate[
                        "scene_index_v9"
                    ] = (
                        candidate_scene_index
                    )

                    candidate[
                        "intrinsic"
                    ] = (
                        candidate[
                            "semantic"
                        ] * 0.36
                        + candidate[
                            "quality"
                        ] * 0.18
                        + candidate[
                            "composition"
                        ] * 0.18
                        + health[
                            "score"
                        ] * 0.28
                    )

                    fallback.append(
                        candidate
                    )

                fallback.sort(
                    key=lambda item: (
                        item[
                            "intrinsic"
                        ]
                    ),
                    reverse=True,
                )

                if not fallback:

                    raise RuntimeError(
                        "V9 recovery found no healthy "
                        f"candidate for beat {beat_index + 1}."
                    )

                accepted = fallback[
                    :5
                ]

                print(
                    "ROLE FALLBACK:",
                    beat_index + 1,
                    "| classifier relaxed; "
                    "visual QA still enforced",
                )

        upgraded.append(
            accepted[
                :8
            ]
        )

        print(
            f"{beat_index + 1:02d}",
            "| accepted:",
            len(
                upgraded[
                    -1
                ]
            ),
            "| rejected:",
            rejected,
            "| best:",
            round(
                float(
                    upgraded[
                        -1
                    ][
                        0
                    ][
                        "intrinsic"
                    ]
                ),
                4,
            ),
            "|",
            VISUAL_BEATS[
                beat_index
            ],
        )

    return upgraded


############################################################
# V9 â€” FINAL ACCEPTANCE GATE
############################################################

def final_qa_v9(
    moments,
):
    semantic = np.array(
        [
            float(
                item[
                    "semantic"
                ]
            )
            for item
            in moments
        ],
        dtype=np.float32,
    )

    quality = np.array(
        [
            float(
                item[
                    "whole_quality"
                ]
            )
            for item
            in moments
        ],
        dtype=np.float32,
    )

    motions = np.array(
        [
            float(
                item[
                    "motion"
                ]
            )
            for item
            in moments
        ],
        dtype=np.float32,
    )

    embeddings = [
        item[
            "embedding"
        ]
        for item
        in moments
    ]

    max_duplicate = 0.0

    duplicate_pairs = 0

    for i in range(
        len(
            embeddings
        )
    ):

        for j in range(
            i + 1,
            len(
                embeddings
            )
        ):

            similarity = float(
                (
                    embeddings[
                        i
                    ]
                    @ embeddings[
                        j
                    ]
                ).item()
            )

            max_duplicate = max(
                max_duplicate,
                similarity,
            )

            if similarity > 0.955:

                duplicate_pairs += 1

    hook = moments[
        0
    ]

    ending = moments[
        -1
    ]

    hook_strength = (
        float(
            hook[
                "semantic"
            ]
        ) * 0.30
        + float(
            hook[
                "composition"
            ]
        ) * 0.25
        + float(
            hook[
                "motion"
            ]
        ) * 0.15
        + float(
            hook[
                "whole_quality"
            ]
        ) * 0.30
    )

    ending_strength = (
        float(
            ending[
                "semantic"
            ]
        ) * 0.30
        + float(
            ending[
                "composition"
            ]
        ) * 0.20
        + float(
            ending[
                "motion"
            ]
        ) * 0.20
        + float(
            ending[
                "whole_quality"
            ]
        ) * 0.30
    )

    print()
    print(
        "========== V9 FINAL EDITORIAL QA =========="
    )

    print(
        "AVG SEMANTIC:",
        round(
            float(
                semantic.mean()
            ),
            4,
        ),
    )

    print(
        "MIN SEMANTIC:",
        round(
            float(
                semantic.min()
            ),
            4,
        ),
    )

    print(
        "AVG WHOLE QUALITY:",
        round(
            float(
                quality.mean()
            ),
            4,
        ),
    )

    print(
        "MIN WHOLE QUALITY:",
        round(
            float(
                quality.min()
            ),
            4,
        ),
    )

    print(
        "HOOK STRENGTH:",
        round(
            float(
                hook_strength
            ),
            4,
        ),
    )

    print(
        "ENDING STRENGTH:",
        round(
            float(
                ending_strength
            ),
            4,
        ),
    )

    print(
        "MAX VISUAL DUPLICATE:",
        round(
            float(
                max_duplicate
            ),
            4,
        ),
    )

    print(
        "DUPLICATE PAIRS:",
        duplicate_pairs,
    )

    print(
        "AVG MOTION:",
        round(
            float(
                motions.mean()
            ),
            4,
        ),
    )

    weak_semantic = int(
        (
            semantic < 0.145
        ).sum()
    )

    weak_quality = int(
        (
            quality < 0.40
        ).sum()
    )

    if weak_semantic > 2:

        raise RuntimeError(
            "V9 QA rejected sequence: "
            "too many weak semantic shots."
        )

    if weak_quality > 1:

        raise RuntimeError(
            "V9 QA rejected sequence: "
            "weak whole-shot quality."
        )

    if duplicate_pairs > 2:

        raise RuntimeError(
            "V9 QA rejected sequence: "
            "too visually repetitive."
        )

    return {
        "hook": hook_strength,
        "ending": ending_strength,
        "semantic": float(
            semantic.mean()
        ),
        "quality": float(
            quality.mean()
        ),
    }


############################################################
# V9 â€” STRONGER CLEAN CAPTIONS
############################################################

def caption_chunks_v9():

    import re

    words = re.sub(
        r"[^\w\s']",
        " ",
        NARRATION,
    ).split()

    groups = []

    pattern = (
        2,
        3,
        3,
        2,
        3,
    )

    cursor = 0

    pattern_index = 0

    while cursor < len(
        words
    ):

        size = pattern[
            pattern_index
            % len(
                pattern
            )
        ]

        group = words[
            cursor:
            cursor + size
        ]

        if not group:

            break

        groups.append(
            " ".join(
                group
            ).upper()
        )

        cursor += size
        pattern_index += 1

    return groups


def caption_schedule_v9(
    voice_duration,
):

    chunks = caption_chunks_v9()

    if not chunks:

        return []

    weights = [
        sum(
            max(
                1.0,
                len(word)
                / 4.5,
            )
            for word
            in chunk.split()
        )
        for chunk
        in chunks
    ]

    total = max(
        sum(
            weights
        ),
        1.0,
    )

    usable = min(
        float(
            voice_duration
        ),
        TARGET_DURATION,
    )

    cursor = 0.0

    output = []

    for chunk, weight in zip(
        chunks,
        weights,
    ):

        duration = (
            usable
            * weight
            / total
        )

        duration = max(
            0.38,
            min(
                1.08,
                duration,
            ),
        )

        end = min(
            usable,
            cursor
            + duration,
        )

        if end <= cursor:

            break

        output.append(
            (
                cursor,
                end,
                chunk,
            )
        )

        cursor = end

        if cursor >= usable:

            break

    return output




############################################################
# V10 â€” SURGICAL RENDER QA
############################################################

def v10_vertical_preview(
    frame,
    focus_ratio: float,
):
    """
    Reproduce the final 9:16 crop on a single frame.

    V10 judges what the viewer will actually see rather than
    only judging the original 1280x534 source frame.
    """

    frame = np.asarray(
        frame
    ).astype(
        np.uint8
    )

    h, w = frame.shape[
        :2
    ]

    scale = max(
        WIDTH / w,
        HEIGHT / h,
    )

    resized_w = int(
        np.ceil(
            w * scale
        )
    )

    resized_h = int(
        np.ceil(
            h * scale
        )
    )

    resized = cv2.resize(
        frame,
        (
            resized_w,
            resized_h,
        ),
        interpolation=(
            cv2.INTER_LANCZOS4
        ),
    )

    focus_ratio = max(
        0.12,
        min(
            0.88,
            float(
                focus_ratio
            ),
        ),
    )

    center_x = (
        resized_w
        * focus_ratio
    )

    half_width = (
        WIDTH / 2
    )

    center_x = max(
        half_width,
        min(
            resized_w
            - half_width,
            center_x,
        ),
    )

    x1 = int(
        round(
            center_x
            - half_width
        )
    )

    x1 = max(
        0,
        min(
            resized_w
            - WIDTH,
            x1,
        ),
    )

    y1 = max(
        0,
        int(
            (
                resized_h
                - HEIGHT
            )
            / 2
        ),
    )

    cropped = resized[
        y1:
        y1 + HEIGHT,
        x1:
        x1 + WIDTH,
    ]

    if (
        cropped.shape[
            0
        ]
        != HEIGHT
        or cropped.shape[
            1
        ]
        != WIDTH
    ):

        cropped = cv2.resize(
            cropped,
            (
                WIDTH,
                HEIGHT,
            ),
            interpolation=(
                cv2.INTER_LANCZOS4
            ),
        )

    return cropped


def v10_frame_metrics(
    frame,
):
    """
    Viewer-facing frame quality.

    Explicitly measures:
      highlight clipping
      crushed blacks
      contrast
      sharpness
      texture / information density
    """

    gray = cv2.cvtColor(
        frame,
        cv2.COLOR_RGB2GRAY,
    )

    brightness = float(
        gray.mean()
    )

    contrast = float(
        gray.std()
    )

    sharpness = float(
        cv2.Laplacian(
            gray,
            cv2.CV_64F,
        ).var()
    )

    blown = float(
        (
            gray >= 248
        ).mean()
    )

    crushed = float(
        (
            gray <= 7
        ).mean()
    )

    ########################################################
    # Texture entropy proxy.
    ########################################################

    histogram = cv2.calcHist(
        [
            gray,
        ],
        [
            0,
        ],
        None,
        [
            64,
        ],
        [
            0,
            256,
        ],
    ).flatten()

    histogram = (
        histogram
        / max(
            float(
                histogram.sum()
            ),
            1.0,
        )
    )

    nonzero = histogram[
        histogram > 0
    ]

    entropy = float(
        -np.sum(
            nonzero
            * np.log2(
                nonzero
            )
        )
    )

    brightness_score = max(
        0.0,
        1.0
        - abs(
            brightness
            - 118.0
        )
        / 118.0,
    )

    contrast_score = min(
        contrast
        / 68.0,
        1.0,
    )

    sharpness_score = min(
        sharpness
        / 260.0,
        1.0,
    )

    entropy_score = min(
        entropy
        / 5.5,
        1.0,
    )

    score = (
        brightness_score
        * 0.15
        + contrast_score
        * 0.22
        + sharpness_score
        * 0.35
        + entropy_score
        * 0.28
    )

    ########################################################
    # Hard visual penalties.
    ########################################################

    score -= min(
        blown
        * 1.8,
        0.45,
    )

    score -= min(
        crushed
        * 0.75,
        0.25,
    )

    # V10.1:
    # Individual frames are advisory.
    # Do not fail an otherwise strong cinematic shot because
    # one frame is slightly soft/dark during motion.

    catastrophic = (
        blown >= 0.42
        or crushed >= 0.82
        or contrast < 7.0
        or entropy < 1.6
    )

    valid = (
        not catastrophic
    )

    return {
        "valid": bool(
            valid
        ),
        "score": float(
            max(
                0.0,
                min(
                    1.0,
                    score,
                ),
            )
        ),
        "brightness": (
            brightness
        ),
        "contrast": (
            contrast
        ),
        "sharpness": (
            sharpness
        ),
        "blown": (
            blown
        ),
        "crushed": (
            crushed
        ),
        "entropy": (
            entropy
        ),
    }


def v10_candidate_render_qa(
    source,
    *,
    candidate,
    entry,
    duration,
    beat_index,
):
    """
    Inspect seven points THROUGHOUT the final proposed shot.

    Crucially, each sample is evaluated AFTER simulated
    vertical cropping.
    """

    timestamp = float(
        candidate[
            "timestamp"
        ]
    )

    scene_start = float(
        entry[
            "start"
        ]
    )

    scene_end = float(
        entry[
            "end"
        ]
    )

    start = max(
        scene_start,
        timestamp
        - duration / 2,
    )

    if (
        start + duration
        > scene_end
    ):

        start = max(
            scene_start,
            scene_end
            - duration,
        )

    end = min(
        scene_end,
        start + duration,
    )

    if (
        end - start
        < duration * 0.60
    ):

        return {
            "valid": False,
            "render_score": 0.0,
            "bad_ratio": 1.0,
            "blown": 1.0,
            "minimum": 0.0,
        }

    times = np.linspace(
        start,
        end,
        7,
    )

    frame_scores = []

    blown_values = []

    invalid_count = 0

    for sample_time in times:

        frame = source.get_frame(
            float(
                sample_time
            )
        ).astype(
            np.uint8
        )

        ####################################################
        # Recalculate framing for THIS frame.
        ####################################################

        _, focus = (
            composition_score(
                frame
            )
        )

        cropped = (
            v10_vertical_preview(
                frame,
                focus,
            )
        )

        metrics = (
            v10_frame_metrics(
                cropped
            )
        )

        frame_scores.append(
            metrics[
                "score"
            ]
        )

        blown_values.append(
            metrics[
                "blown"
            ]
        )

        if not metrics[
            "valid"
        ]:

            invalid_count += 1

    average = float(
        np.mean(
            frame_scores
        )
    )

    minimum = float(
        np.min(
            frame_scores
        )
    )

    lower_quartile = float(
        np.percentile(
            frame_scores,
            25,
        )
    )

    bad_ratio = (
        invalid_count
        / max(
            len(
                frame_scores
            ),
            1,
        )
    )

    blown = float(
        np.mean(
            blown_values
        )
    )

    render_score = (
        average * 0.57
        + lower_quartile * 0.28
        + minimum * 0.15
    )

    ########################################################
    # Face/reaction beats:
    #
    # V9 already produced CLIP role margins. V10 makes a
    # substantially negative face margin expensive rather
    # than letting a high quality back-of-head/object shot
    # survive.
    ########################################################

    face_margin = float(
        candidate.get(
            "face_margin",
            0.0,
        )
    )

    face_penalty = 0.0

    if beat_index in FACE_BEATS:

        if face_margin < -0.08:

            face_penalty = 0.20

        elif face_margin < -0.04:

            face_penalty = 0.10

        elif face_margin < 0.0:

            face_penalty = 0.04

    render_score -= (
        face_penalty
    )

    # V10.1 whole-shot calibration.
    #
    # Aggregate quality is more important than one imperfect
    # sample. Hard failures remain protected.

    valid = (
        bad_ratio <= 0.58
        and blown < 0.18
        and minimum >= 0.18
        and render_score >= 0.50
    )

    # Face beats still get protection, but the CLIP face
    # classifier is not reliable enough to hard-fail every
    # mildly negative margin.
    if (
        beat_index in FACE_BEATS
        and face_margin < -0.16
    ):
        valid = False

    return {
        "valid": bool(
            valid
        ),
        "render_score": float(
            max(
                0.0,
                render_score,
            )
        ),
        "bad_ratio": (
            bad_ratio
        ),
        "blown": blown,
        "minimum": minimum,
        "face_margin": (
            face_margin
        ),
    }


############################################################
# V10 â€” SURGICAL SHOT REPLACEMENT
############################################################

def polish_sequence_v10(
    source,
    entries,
    selected,
    candidate_pools,
    optimized_moments,
):
    """
    Preserve good V9 decisions.

    Replace ONLY shots that fail the final viewer-facing QA.

    This prevents V10 from destroying the sequence that got
    V9 to ~9.1.
    """

    print()
    print(
        "========== V10.1 RENDERED-FRAME QA =========="
    )

    polished = []

    replacements = 0

    for beat_index, current in enumerate(
        optimized_moments
    ):

        original_scene_index = int(
            current.get(
                "scene_index_v9",
                selected[
                    beat_index
                ],
            )
        )

        original_entry = entries[
            original_scene_index
        ]

        current_qa = (
            v10_candidate_render_qa(
                source,
                candidate=current,
                entry=original_entry,
                duration=float(
                    SHOT_DURATIONS[
                        beat_index
                    ]
                ),
                beat_index=beat_index,
            )
        )

        ####################################################
        # If V9's selected shot passes strongly, KEEP IT.
        ####################################################

        if current_qa[
            "valid"
        ]:

            current = dict(
                current
            )

            current[
                "v10_render_score"
            ] = current_qa[
                "render_score"
            ]

            polished.append(
                current
            )

            print(
                f"{beat_index + 1:02d}",
                "| KEEP",
                "| RENDER:",
                round(
                    current_qa[
                        "render_score"
                    ],
                    3,
                ),
                "| BLOWN:",
                round(
                    current_qa[
                        "blown"
                    ],
                    3,
                ),
                "| FACE:",
                round(
                    current_qa[
                        "face_margin"
                    ],
                    3,
                ),
            )

            continue

        ####################################################
        # Weak V9 shot:
        # search the existing editorially-approved pool.
        ####################################################

        best = None
        best_total = -999.0
        best_qa = None

        previous_embedding = (
            polished[
                -1
            ][
                "embedding"
            ]
            if polished
            else None
        )

        next_embedding = None

        if (
            beat_index + 1
            < len(
                optimized_moments
            )
        ):

            next_embedding = (
                optimized_moments[
                    beat_index + 1
                ][
                    "embedding"
                ]
            )

        for alternative in candidate_pools[
            beat_index
        ]:

            alternative_scene_index = int(
                alternative.get(
                    "scene_index_v9",
                    selected[
                        beat_index
                    ],
                )
            )

            entry = entries[
                alternative_scene_index
            ]

            qa = (
                v10_candidate_render_qa(
                    source,
                    candidate=alternative,
                    entry=entry,
                    duration=float(
                        SHOT_DURATIONS[
                            beat_index
                        ]
                    ),
                    beat_index=beat_index,
                )
            )

            if not qa[
                "valid"
            ]:

                continue

            ################################################
            # Preserve sequence continuity.
            ################################################

            continuity_penalty = 0.0

            if (
                previous_embedding
                is not None
            ):

                similarity = float(
                    (
                        alternative[
                            "embedding"
                        ]
                        @ previous_embedding
                    ).item()
                )

                if similarity > 0.95:

                    continuity_penalty += (
                        similarity
                        - 0.95
                    ) * 1.7

            if (
                next_embedding
                is not None
            ):

                similarity = float(
                    (
                        alternative[
                            "embedding"
                        ]
                        @ next_embedding
                    ).item()
                )

                if similarity > 0.95:

                    continuity_penalty += (
                        similarity
                        - 0.95
                    ) * 1.2

            intrinsic = float(
                alternative.get(
                    "intrinsic",
                    alternative.get(
                        "score",
                        0.0,
                    ),
                )
            )

            semantic = float(
                alternative.get(
                    "semantic",
                    0.0,
                )
            )

            composition = float(
                alternative.get(
                    "composition",
                    0.0,
                )
            )

            total = (
                qa[
                    "render_score"
                ] * 0.46
                + intrinsic * 0.30
                + semantic * 0.14
                + composition * 0.10
                - continuity_penalty
            )

            if total > best_total:

                best_total = total
                best = alternative
                best_qa = qa

        ####################################################
        # If no better alternative survives, keep V9's shot
        # rather than silently choosing something worse.
        ####################################################

        if best is None:

            current = dict(
                current
            )

            current[
                "v10_render_score"
            ] = current_qa[
                "render_score"
            ]

            polished.append(
                current
            )

            print(
                f"{beat_index + 1:02d}",
                "| WARN KEEP",
                "| no superior replacement",
                "| RENDER:",
                round(
                    current_qa[
                        "render_score"
                    ],
                    3,
                ),
            )

            continue

        best = dict(
            best
        )

        best[
            "v10_render_score"
        ] = best_qa[
            "render_score"
        ]

        polished.append(
            best
        )

        replacements += 1

        print(
            f"{beat_index + 1:02d}",
            "| REPLACED",
            "| OLD:",
            round(
                current_qa[
                    "render_score"
                ],
                3,
            ),
            "| NEW:",
            round(
                best_qa[
                    "render_score"
                ],
                3,
            ),
            "| SEM:",
            round(
                float(
                    best[
                        "semantic"
                    ]
                ),
                3,
            ),
            "| FACE:",
            round(
                best_qa[
                    "face_margin"
                ],
                3,
            ),
        )

    print()
    print(
        "V10 TOTAL REPLACEMENTS:",
        replacements,
    )

    return polished


############################################################
# V10 â€” FINAL POLISH QA
############################################################

def final_polish_qa_v10(
    source,
    entries,
    selected,
    moments,
):
    print()
    print(
        "========== V10.1 FINAL POLISH QA =========="
    )

    render_scores = []

    failures = []

    blown_values = []

    for beat_index, moment in enumerate(
        moments
    ):

        scene_index = int(
            moment.get(
                "scene_index_v9",
                selected[
                    beat_index
                ],
            )
        )

        entry = entries[
            scene_index
        ]

        qa = (
            v10_candidate_render_qa(
                source,
                candidate=moment,
                entry=entry,
                duration=float(
                    SHOT_DURATIONS[
                        beat_index
                    ]
                ),
                beat_index=beat_index,
            )
        )

        render_scores.append(
            qa[
                "render_score"
            ]
        )

        blown_values.append(
            qa[
                "blown"
            ]
        )

        if not qa[
            "valid"
        ]:

            failures.append(
                beat_index + 1
            )

    average = float(
        np.mean(
            render_scores
        )
    )

    minimum = float(
        np.min(
            render_scores
        )
    )

    average_blown = float(
        np.mean(
            blown_values
        )
    )

    print(
        "AVG RENDER QUALITY:",
        round(
            average,
            4,
        ),
    )

    print(
        "MIN RENDER QUALITY:",
        round(
            minimum,
            4,
        ),
    )

    print(
        "AVG BLOWN PIXELS:",
        round(
            average_blown,
            4,
        ),
    )

    print(
        "FAILED BEATS:",
        failures,
    )

    ########################################################
    # V10 should still finish if ONE stubborn classifier
    # issue remains, but multiple viewer-visible failures
    # means the edit should be rejected.
    ########################################################

    # V10.1:
    # Reject only when the sequence genuinely contains too
    # many weak viewer-facing shots.

    if len(
        failures
    ) > 4:

        raise RuntimeError(
            "V10.1 final polish QA rejected the edit. "
            f"Failed beats: {failures}"
        )

    if average < 0.50:

        raise RuntimeError(
            "V10.1 final polish QA rejected the edit: "
            "average render quality too low."
        )

    return {
        "average_render_quality": (
            average
        ),
        "minimum_render_quality": (
            minimum
        ),
        "failed_beats": failures,
    }


############################################################
# V10 â€” CAPTIONS THAT SPAN THE FULL VOICE
############################################################

def caption_chunks_v10():
    """
    Shorter, cleaner 2-3 word caption groups.
    """

    import re

    words = re.sub(
        r"[^\w\s']",
        " ",
        NARRATION,
    ).split()

    pattern = (
        2,
        3,
        3,
        2,
        3,
        2,
    )

    groups = []

    cursor = 0
    pattern_index = 0

    while cursor < len(
        words
    ):

        size = pattern[
            pattern_index
            % len(
                pattern
            )
        ]

        group = words[
            cursor:
            cursor + size
        ]

        if not group:
            break

        groups.append(
            " ".join(
                group
            ).upper()
        )

        cursor += size
        pattern_index += 1

    return groups


def caption_schedule_v10(
    voice_duration,
):
    """
    Unlike earlier caption schedulers, this schedule always
    fills the available narration duration exactly.

    No cumulative 1.08-second cap causing captions to finish
    before the voice.
    """

    chunks = (
        caption_chunks_v10()
    )

    if not chunks:
        return []

    usable = min(
        float(
            voice_duration
        ),
        TARGET_DURATION,
    )

    weights = []

    for chunk in chunks:

        words = chunk.split()

        weight = sum(
            max(
                1.0,
                len(word)
                / 4.6,
            )
            for word
            in words
        )

        weights.append(
            weight
        )

    cumulative = np.cumsum(
        [
            0.0,
            *weights,
        ],
        dtype=np.float64,
    )

    total = max(
        float(
            cumulative[
                -1
            ]
        ),
        1.0,
    )

    boundaries = (
        cumulative
        / total
        * usable
    )

    schedule = []

    for index, chunk in enumerate(
        chunks
    ):

        start = float(
            boundaries[
                index
            ]
        )

        end = float(
            boundaries[
                index + 1
            ]
        )

        if end <= start:
            continue

        schedule.append(
            (
                start,
                end,
                chunk,
            )
        )

    return schedule




############################################################
# V11 â€” FINAL EDITORIAL ENGINE
############################################################

V11_BEAM_WIDTH = 120
V11_POOL_LIMIT = 8

V11_HARD_DUPLICATE = 0.972
V11_SOFT_DUPLICATE = 0.905

V11_MIN_RENDER_SCORE = 0.40

V11_MAX_BACKWARD_NORMAL = 18.0


############################################################
# V11 â€” IMPROVED SUBJECT TRACKING
############################################################

def build_focus_track_v11(
    source,
    *,
    start: float,
    end: float,
):
    """
    Stable subject-aware camera path.

    Improvements over V8:
      - more temporal samples
      - wider median smoothing
      - exponential smoothing
      - dead zone
      - maximum camera movement per sample
      - suppresses robotic crop hunting
    """

    if end <= start:

        return [
            (
                0.0,
                0.5,
            )
        ]

    times = np.linspace(
        start,
        end,
        15,
    )

    raw = []

    for timestamp in times:

        frame = source.get_frame(
            float(timestamp)
        ).astype(
            np.uint8
        )

        _, focus = composition_score(
            frame
        )

        raw.append(
            max(
                0.12,
                min(
                    0.88,
                    float(focus),
                ),
            )
        )

    ########################################################
    # 5-sample median smoothing
    ########################################################

    median_values = []

    for index in range(
        len(raw)
    ):

        left = max(
            0,
            index - 2,
        )

        right = min(
            len(raw),
            index + 3,
        )

        median_values.append(
            float(
                np.median(
                    raw[
                        left:right
                    ]
                )
            )
        )

    ########################################################
    # Exponential smoothing
    ########################################################

    alpha = 0.36

    smooth = [
        median_values[
            0
        ]
    ]

    for value in median_values[
        1:
    ]:

        previous = smooth[
            -1
        ]

        smooth.append(
            previous
            + alpha
            * (
                value
                - previous
            )
        )

    ########################################################
    # Cinematic dead zone + movement limiter
    ########################################################

    stable = [
        smooth[
            0
        ]
    ]

    DEAD_ZONE = 0.025
    MAX_STEP = 0.042

    for target in smooth[
        1:
    ]:

        current = stable[
            -1
        ]

        delta = (
            target
            - current
        )

        if abs(
            delta
        ) <= DEAD_ZONE:

            stable.append(
                current
            )

            continue

        delta = max(
            -MAX_STEP,
            min(
                MAX_STEP,
                delta,
            ),
        )

        stable.append(
            max(
                0.12,
                min(
                    0.88,
                    current
                    + delta,
                ),
            )
        )

    return [
        (
            float(
                timestamp
                - start
            ),
            float(
                focus
            ),
        )
        for timestamp, focus
        in zip(
            times,
            stable,
        )
    ]


############################################################
# V11 â€” PREPARE EDITORIAL CANDIDATES
############################################################

def prepare_candidate_pools_v11(
    source,
    entries,
    selected,
    candidate_pools,
    current_moments,
):
    """
    Re-evaluate every editorially approved candidate through
    the viewer-facing V10 crop QA.

    V11 then gives the global optimizer several genuinely
    usable choices for each beat.
    """

    print()
    print(
        "========== V11 CANDIDATE PREPARATION =========="
    )

    output = []

    for beat_index, pool in enumerate(
        candidate_pools
    ):

        combined = list(
            pool
        )

        ####################################################
        # Guarantee V10's chosen shot remains an option.
        ####################################################

        combined.append(
            current_moments[
                beat_index
            ]
        )

        prepared = []

        seen = set()

        for candidate in combined:

            scene_index = int(
                candidate.get(
                    "scene_index_v9",
                    selected[
                        beat_index
                    ],
                )
            )

            timestamp = float(
                candidate[
                    "timestamp"
                ]
            )

            identity = (
                scene_index,
                round(
                    timestamp,
                    2,
                ),
            )

            if identity in seen:

                continue

            seen.add(
                identity
            )

            entry = entries[
                scene_index
            ]

            qa = (
                v10_candidate_render_qa(
                    source,
                    candidate=candidate,
                    entry=entry,
                    duration=float(
                        SHOT_DURATIONS[
                            beat_index
                        ]
                    ),
                    beat_index=beat_index,
                )
            )

            candidate = dict(
                candidate
            )

            candidate[
                "scene_index_v9"
            ] = scene_index

            candidate[
                "v11_render_score"
            ] = float(
                qa[
                    "render_score"
                ]
            )

            candidate[
                "v11_blown"
            ] = float(
                qa[
                    "blown"
                ]
            )

            candidate[
                "v11_bad_ratio"
            ] = float(
                qa[
                    "bad_ratio"
                ]
            )

            ################################################
            # Do not instantly discard moderately imperfect
            # shots. Penalize them instead.
            ################################################

            semantic = float(
                candidate.get(
                    "semantic",
                    0.0,
                )
            )

            composition = float(
                candidate.get(
                    "composition",
                    0.0,
                )
            )

            motion = float(
                candidate.get(
                    "motion",
                    0.0,
                )
            )

            whole = float(
                candidate.get(
                    "whole_quality",
                    0.0,
                )
            )

            intrinsic = float(
                candidate.get(
                    "intrinsic",
                    candidate.get(
                        "score",
                        0.0,
                    ),
                )
            )

            energy_match = float(
                candidate.get(
                    "energy_match",
                    0.5,
                )
            )

            render_score = float(
                qa[
                    "render_score"
                ]
            )

            ################################################
            # Local editorial score
            ################################################

            local = (
                render_score
                * 0.30

                + intrinsic
                * 0.21

                + semantic
                * 0.18

                + composition
                * 0.11

                + whole
                * 0.10

                + energy_match
                * 0.06

                + motion
                * 0.04
            )

            ################################################
            # Viewer-visible quality penalty
            ################################################

            if (
                render_score
                < V11_MIN_RENDER_SCORE
            ):

                local -= (
                    V11_MIN_RENDER_SCORE
                    - render_score
                ) * 0.85

            ################################################
            # Face beats
            ################################################

            if beat_index in FACE_BEATS:

                face_margin = float(
                    candidate.get(
                        "face_margin",
                        0.0,
                    )
                )

                if face_margin < -0.14:

                    local -= 0.13

                elif face_margin < -0.07:

                    local -= 0.07

                elif face_margin > 0.03:

                    local += 0.035

            ################################################
            # Action beats
            ################################################

            if beat_index in ACTION_BEATS:

                action_margin = float(
                    candidate.get(
                        "action_margin",
                        0.0,
                    )
                )

                local += max(
                    -0.03,
                    min(
                        0.05,
                        action_margin
                        * 0.10,
                    ),
                )

                if motion < 0.08:

                    local -= 0.055

            ################################################
            # Hook
            ################################################

            if beat_index == 0:

                local += (
                    motion
                    * 0.07
                )

                local += (
                    render_score
                    * 0.06
                )

                local += (
                    float(
                        candidate.get(
                            "hook_margin",
                            0.0,
                        )
                    )
                    * 0.10
                )

            ################################################
            # Ending
            ################################################

            if (
                beat_index
                == len(
                    candidate_pools
                ) - 1
            ):

                local += (
                    motion
                    * 0.08
                )

                local += (
                    render_score
                    * 0.08
                )

                local += (
                    float(
                        candidate.get(
                            "ending_margin",
                            0.0,
                        )
                    )
                    * 0.12
                )

            candidate[
                "v11_local_score"
            ] = float(
                local
            )

            prepared.append(
                candidate
            )

        prepared.sort(
            key=lambda item: (
                item[
                    "v11_local_score"
                ]
            ),
            reverse=True,
        )

        if not prepared:

            raise RuntimeError(
                "V11 has no candidates for beat "
                f"{beat_index + 1}."
            )

        prepared = prepared[
            :V11_POOL_LIMIT
        ]

        output.append(
            prepared
        )

        print(
            f"{beat_index + 1:02d}",
            "| candidates:",
            len(
                prepared
            ),
            "| local:",
            round(
                prepared[
                    0
                ][
                    "v11_local_score"
                ],
                4,
            ),
            "| render:",
            round(
                prepared[
                    0
                ][
                    "v11_render_score"
                ],
                3,
            ),
            "| semantic:",
            round(
                float(
                    prepared[
                        0
                    ].get(
                        "semantic",
                        0.0,
                    )
                ),
                3,
            ),
        )

    return output


############################################################
# V11 â€” GLOBAL EDITORIAL BEAM SEARCH
############################################################

def optimize_sequence_v11(
    pools,
):
    """
    Optimize the COMPLETE edit.

    Judges:
      - local visual quality
      - semantics
      - duplicate compositions
      - chronology
      - motion progression
      - visual novelty
      - continuity
      - hook
      - climax
    """

    print()
    print(
        "========== V11 GLOBAL EDITOR =========="
    )

    beam = []

    ########################################################
    # Start with every hook candidate.
    ########################################################

    for candidate in pools[
        0
    ]:

        score = float(
            candidate[
                "v11_local_score"
            ]
        )

        beam.append(
            (
                score,
                [
                    candidate
                ],
            )
        )

    beam.sort(
        key=lambda state: (
            state[
                0
            ]
        ),
        reverse=True,
    )

    beam = beam[
        :V11_BEAM_WIDTH
    ]

    ########################################################
    # Extend full sequence
    ########################################################

    for beat_index in range(
        1,
        len(
            pools
        ),
    ):

        next_beam = []

        for total, sequence in beam:

            previous = sequence[
                -1
            ]

            previous_timestamp = float(
                previous[
                    "timestamp"
                ]
            )

            previous_motion = float(
                previous.get(
                    "motion",
                    0.0,
                )
            )

            previous_focus = float(
                previous.get(
                    "focus_x",
                    0.5,
                )
            )

            prior_embeddings = [
                item[
                    "embedding"
                ]
                for item
                in sequence
            ]

            for candidate in pools[
                beat_index
            ]:

                timestamp = float(
                    candidate[
                        "timestamp"
                    ]
                )

                motion = float(
                    candidate.get(
                        "motion",
                        0.0,
                    )
                )

                focus = float(
                    candidate.get(
                        "focus_x",
                        0.5,
                    )
                )

                ################################################
                # Duplicate / composition similarity
                ################################################

                similarities = [
                    float(
                        (
                            candidate[
                                "embedding"
                            ]
                            @ embedding
                        ).item()
                    )
                    for embedding
                    in prior_embeddings
                ]

                max_similarity = max(
                    similarities
                )

                if (
                    max_similarity
                    >= V11_HARD_DUPLICATE
                ):

                    continue

                duplicate_penalty = 0.0

                if (
                    max_similarity
                    > V11_SOFT_DUPLICATE
                ):

                    duplicate_penalty = (
                        max_similarity
                        - V11_SOFT_DUPLICATE
                    ) * 1.05

                adjacent_similarity = float(
                    (
                        candidate[
                            "embedding"
                        ]
                        @ previous[
                            "embedding"
                        ]
                    ).item()
                )

                ################################################
                # Chronological continuity.
                #
                # Ending is allowed to jump for a stronger
                # payoff, but normal story beats strongly prefer
                # moving forward.
                ################################################

                delta_time = (
                    timestamp
                    - previous_timestamp
                )

                chronology_penalty = 0.0

                is_final = (
                    beat_index
                    == len(
                        pools
                    ) - 1
                )

                if not is_final:

                    if (
                        delta_time
                        < -V11_MAX_BACKWARD_NORMAL
                    ):

                        continue

                    if delta_time < 0:

                        chronology_penalty += (
                            abs(
                                delta_time
                            )
                            / 80.0
                        ) * 0.16

                    if delta_time > 95:

                        chronology_penalty += (
                            delta_time
                            - 95
                        ) / 400.0

                ################################################
                # Motion curve
                ################################################

                desired_motion = float(
                    ENERGY_CURVE[
                        beat_index
                    ]
                )

                motion_match = max(
                    0.0,
                    1.0
                    - abs(
                        motion
                        - desired_motion
                    ),
                )

                desired_change = (
                    float(
                        ENERGY_CURVE[
                            beat_index
                        ]
                    )
                    - float(
                        ENERGY_CURVE[
                            beat_index - 1
                        ]
                    )
                )

                actual_change = (
                    motion
                    - previous_motion
                )

                motion_transition = max(
                    0.0,
                    1.0
                    - abs(
                        desired_change
                        - actual_change
                    ),
                )

                ################################################
                # Camera jump penalty
                ################################################

                focus_jump = abs(
                    focus
                    - previous_focus
                )

                focus_penalty = max(
                    0.0,
                    focus_jump
                    - 0.30,
                ) * 0.10

                ################################################
                # Encourage a real cut without rewarding total
                # visual randomness.
                ################################################

                novelty = max(
                    0.0,
                    min(
                        1.0,
                        1.0
                        - adjacent_similarity,
                    ),
                )

                novelty_score = (
                    novelty
                    * 0.035
                )

                ################################################
                # Final incremental score
                ################################################

                increment = (
                    float(
                        candidate[
                            "v11_local_score"
                        ]
                    )

                    + motion_match
                    * 0.055

                    + motion_transition
                    * 0.035

                    + novelty_score

                    - duplicate_penalty

                    - chronology_penalty

                    - focus_penalty
                )

                ################################################
                # Climax bonus
                ################################################

                if is_final:

                    increment += (
                        float(
                            candidate.get(
                                "v11_render_score",
                                0.0,
                            )
                        )
                        * 0.075
                    )

                    increment += (
                        motion
                        * 0.055
                    )

                next_beam.append(
                    (
                        total
                        + increment,
                        sequence
                        + [
                            candidate
                        ],
                    )
                )

        if not next_beam:

            raise RuntimeError(
                "V11 global editor exhausted "
                f"at beat {beat_index + 1}."
            )

        next_beam.sort(
            key=lambda state: (
                state[
                    0
                ]
            ),
            reverse=True,
        )

        beam = next_beam[
            :V11_BEAM_WIDTH
        ]

    best_score, sequence = (
        beam[
            0
        ]
    )

    print(
        "V11 GLOBAL SCORE:",
        round(
            float(
                best_score
            ),
            4,
        ),
    )

    print()

    for index, candidate in enumerate(
        sequence,
        start=1,
    ):

        print(
            f"{index:02d}",
            "|",
            round(
                float(
                    candidate[
                        "timestamp"
                    ]
                ),
                2,
            ),
            "sec",
            "| SEM:",
            round(
                float(
                    candidate.get(
                        "semantic",
                        0.0,
                    )
                ),
                3,
            ),
            "| RENDER:",
            round(
                float(
                    candidate.get(
                        "v11_render_score",
                        0.0,
                    )
                ),
                3,
            ),
            "| MOT:",
            round(
                float(
                    candidate.get(
                        "motion",
                        0.0,
                    )
                ),
                3,
            ),
        )

    return sequence


############################################################
# V11 â€” NON-DESTRUCTIVE FINAL QA
############################################################

def final_editorial_qa_v11(
    moments,
):
    """
    Final sequence diagnostics.

    This deliberately avoids V10's previous failure mode where
    one over-strict condition rejected every shot.
    """

    print()
    print(
        "========== V11 FINAL EDITORIAL QA =========="
    )

    render_scores = np.array(
        [
            float(
                item.get(
                    "v11_render_score",
                    0.0,
                )
            )
            for item
            in moments
        ],
        dtype=np.float32,
    )

    semantic_scores = np.array(
        [
            float(
                item.get(
                    "semantic",
                    0.0,
                )
            )
            for item
            in moments
        ],
        dtype=np.float32,
    )

    motions = np.array(
        [
            float(
                item.get(
                    "motion",
                    0.0,
                )
            )
            for item
            in moments
        ],
        dtype=np.float32,
    )

    ########################################################
    # Duplicate analysis
    ########################################################

    duplicate_pairs = 0
    max_duplicate = 0.0

    for left in range(
        len(
            moments
        )
    ):

        for right in range(
            left + 1,
            len(
                moments
            )
        ):

            similarity = float(
                (
                    moments[
                        left
                    ][
                        "embedding"
                    ]
                    @ moments[
                        right
                    ][
                        "embedding"
                    ]
                ).item()
            )

            max_duplicate = max(
                max_duplicate,
                similarity,
            )

            if similarity > 0.95:

                duplicate_pairs += 1

    ########################################################
    # Chronology
    ########################################################

    backward_jumps = []

    for index in range(
        1,
        len(
            moments
        ) - 1,
    ):

        previous = float(
            moments[
                index - 1
            ][
                "timestamp"
            ]
        )

        current = float(
            moments[
                index
            ][
                "timestamp"
            ]
        )

        if current < (
            previous - 8.0
        ):

            backward_jumps.append(
                (
                    index + 1,
                    round(
                        previous
                        - current,
                        2,
                    ),
                )
            )

    weak = [
        index + 1
        for index, score
        in enumerate(
            render_scores
        )
        if score < 0.43
    ]

    print(
        "AVG RENDER:",
        round(
            float(
                render_scores.mean()
            ),
            4,
        ),
    )

    print(
        "MIN RENDER:",
        round(
            float(
                render_scores.min()
            ),
            4,
        ),
    )

    print(
        "AVG SEMANTIC:",
        round(
            float(
                semantic_scores.mean()
            ),
            4,
        ),
    )

    print(
        "AVG MOTION:",
        round(
            float(
                motions.mean()
            ),
            4,
        ),
    )

    print(
        "MAX DUPLICATE:",
        round(
            max_duplicate,
            4,
        ),
    )

    print(
        "DUPLICATE PAIRS:",
        duplicate_pairs,
    )

    print(
        "BACKWARD JUMPS:",
        backward_jumps,
    )

    print(
        "WEAK VIEWER SHOTS:",
        weak,
    )

    ########################################################
    # Internal editorial confidence.
    #
    # This is NOT a human /10 rating.
    ########################################################

    confidence = (
        float(
            render_scores.mean()
        ) * 0.48

        + min(
            float(
                semantic_scores.mean()
            ) / 0.30,
            1.0,
        ) * 0.22

        + min(
            float(
                motions.mean()
            ) / 0.70,
            1.0,
        ) * 0.12

        + max(
            0.0,
            1.0
            - max_duplicate,
        ) * 0.18
    )

    print(
        "V11 INTERNAL EDITORIAL CONFIDENCE:",
        round(
            confidence,
            4,
        ),
    )

    ########################################################
    # Only catastrophic failure blocks the render.
    ########################################################

    if len(
        weak
    ) > 5:

        raise RuntimeError(
            "V11 rejected: too many genuinely "
            f"weak viewer shots: {weak}"
        )

    if (
        float(
            render_scores.mean()
        )
        < 0.47
    ):

        raise RuntimeError(
            "V11 rejected: average viewer-facing "
            "quality is too low."
        )

    if duplicate_pairs > 4:

        raise RuntimeError(
            "V11 rejected: sequence is too repetitive."
        )

    return {
        "average_render": float(
            render_scores.mean()
        ),
        "minimum_render": float(
            render_scores.min()
        ),
        "duplicate_pairs": (
            duplicate_pairs
        ),
        "backward_jumps": (
            backward_jumps
        ),
        "weak": weak,
    }


############################################################
# V11 â€” BETTER CAPTION SEGMENTATION
############################################################

def caption_chunks_v11():
    """
    Modern Shorts caption groups:
      mostly 2-3 words
      punctuation-aware
      avoids long text blocks
    """

    import re

    words = re.findall(
        r"[A-Za-z0-9']+|[,.!?;:]",
        NARRATION,
    )

    chunks = []

    current = []

    target_pattern = (
        3,
        2,
        3,
        3,
        2,
    )

    pattern_index = 0

    for token in words:

        if token in {
            ".",
            ",",
            "!",
            "?",
            ";",
            ":",
        }:

            if current:

                chunks.append(
                    " ".join(
                        current
                    ).upper()
                )

                current = []

                pattern_index += 1

            continue

        current.append(
            token
        )

        target = target_pattern[
            pattern_index
            % len(
                target_pattern
            )
        ]

        if len(
            current
        ) >= target:

            chunks.append(
                " ".join(
                    current
                ).upper()
            )

            current = []

            pattern_index += 1

    if current:

        chunks.append(
            " ".join(
                current
            ).upper()
        )

    return [
        chunk
        for chunk
        in chunks
        if chunk.strip()
    ]


def caption_schedule_v11(
    voice_duration,
):
    """
    Weighted narration timing with subtle cut alignment.

    This remains approximation because Piper does not provide
    true word timestamps here, but it is more stable than
    arbitrary fixed-duration caption cards.
    """

    chunks = (
        caption_chunks_v11()
    )

    if not chunks:

        return []

    usable = min(
        float(
            voice_duration
        ),
        TARGET_DURATION,
    )

    ########################################################
    # Weight longer words slightly more because they usually
    # take longer to speak.
    ########################################################

    weights = []

    for chunk in chunks:

        words = chunk.split()

        weight = sum(
            0.75
            + min(
                len(word),
                10,
            ) / 7.0
            for word
            in words
        )

        weights.append(
            weight
        )

    total = max(
        float(
            sum(
                weights
            )
        ),
        1.0,
    )

    cumulative = 0.0

    boundaries = [
        0.0
    ]

    for weight in weights:

        cumulative += weight

        boundaries.append(
            usable
            * cumulative
            / total
        )

    ########################################################
    # Shot cuts
    ########################################################

    cuts = [
        0.0
    ]

    position = 0.0

    for duration in SHOT_DURATIONS:

        position += float(
            duration
        )

        cuts.append(
            position
        )

    ########################################################
    # Snap caption changes to a nearby visual cut only when
    # the difference is tiny. Do NOT noticeably desync speech.
    ########################################################

    snapped = [
        boundaries[
            0
        ]
    ]

    for boundary in boundaries[
        1:-1
    ]:

        nearest = min(
            cuts,
            key=lambda cut: abs(
                cut
                - boundary
            ),
        )

        if abs(
            nearest
            - boundary
        ) <= 0.11:

            boundary = nearest

        snapped.append(
            boundary
        )

    snapped.append(
        usable
    )

    schedule = []

    for index, chunk in enumerate(
        chunks
    ):

        start = float(
            snapped[
                index
            ]
        )

        end = float(
            snapped[
                index + 1
            ]
        )

        if (
            end - start
            < 0.18
        ):

            continue

        schedule.append(
            (
                start,
                end,
                chunk,
            )
        )

    return schedule




############################################################
# V12 â€” PRESENTATION POLISH
############################################################

V12_FONT_PATH = Path(
    r"C:\Windows\Fonts\arialbd.ttf"
)

V12_FONT = (
    str(
        V12_FONT_PATH
    )
    if V12_FONT_PATH.is_file()
    else None
)



############################################################
# V13 â€” STORY-FIRST NARRATIVE ENGINE
############################################################

V13_BANNED_META_PHRASES = (
    "wide shot",
    "reaction shot",
    "close up",
    "close-up",
    "medium shot",
    "camera",
    "footage",
    "sequence works",
    "jumping between",
    "visual beat",
    "visual beats",
    "cinematic shot",
    "establishing shot",
    "danger shots",
    "the edit",
    "editing",
)

V13_TARGET_WORDS_MIN = 72
V13_TARGET_WORDS_MAX = 94


############################################################
# STORY PHASES
############################################################

def story_phase_v13(
    beat_index,
    total,
):

    ratio = (
        beat_index
        / max(
            total - 1,
            1,
        )
    )

    if ratio < 0.14:
        return "HOOK"

    if ratio < 0.34:
        return "SETUP"

    if ratio < 0.56:
        return "COMPLICATION"

    if ratio < 0.82:
        return "ESCALATION"

    return "PAYOFF"


############################################################
# CLEAN VISUAL DESCRIPTION
############################################################

def clean_visual_description_v13(
    description,
):
    """
    Convert editor terminology into story information.

    We deliberately remove words that encourage the narrator
    to describe cinematography instead of events.
    """

    import re

    value = str(
        description
    ).lower()

    replacements = (
        ("wide cinematic", ""),
        ("cinematic", ""),
        ("establishing shot", ""),
        ("medium shot", ""),
        ("close up", ""),
        ("close-up", ""),
        ("reaction shot", ""),
        ("dramatic", ""),
        ("extreme", ""),
        ("shot", ""),
        ("visual", ""),
    )

    for old, new in replacements:

        value = value.replace(
            old,
            new,
        )

    value = re.sub(
        r"\s+",
        " ",
        value,
    ).strip()

    return value


############################################################
# EXTRACT WHAT FINAL EDIT ACTUALLY SHOWS
############################################################

def build_story_evidence_v13(
    optimized_moments,
):
    evidence = []

    total = len(
        optimized_moments
    )

    for index, moment in enumerate(
        optimized_moments
    ):

        original = (
            VISUAL_BEATS[
                index
            ]
            if index
            < len(
                VISUAL_BEATS
            )
            else "science fiction action"
        )

        evidence.append(
            {
                "beat": index + 1,
                "phase": story_phase_v13(
                    index,
                    total,
                ),
                "description":
                    clean_visual_description_v13(
                        original
                    ),
                "timestamp": float(
                    moment.get(
                        "timestamp",
                        0.0,
                    )
                ),
                "semantic": float(
                    moment.get(
                        "semantic",
                        0.0,
                    )
                ),
                "motion": float(
                    moment.get(
                        "motion",
                        0.0,
                    )
                ),
                "quality": float(
                    moment.get(
                        "v11_render_score",
                        moment.get(
                            "whole_quality",
                            0.0,
                        ),
                    )
                ),
            }
        )

    return evidence


############################################################
# COLLAPSE 22 SHOTS INTO MEANINGFUL STORY EVENTS
############################################################

def build_story_events_v13(
    evidence,
):
    """
    The edit can contain 22 shots without requiring 22
    narration statements.

    Collapse them into five story phases.
    """

    phases = (
        "HOOK",
        "SETUP",
        "COMPLICATION",
        "ESCALATION",
        "PAYOFF",
    )

    events = []

    for phase in phases:

        group = [
            item
            for item
            in evidence
            if item[
                "phase"
            ] == phase
        ]

        if not group:
            continue

        ####################################################
        # Rank the most informative descriptions.
        ####################################################

        ranked = sorted(
            group,
            key=lambda item: (
                item[
                    "semantic"
                ] * 0.38
                + item[
                    "quality"
                ] * 0.34
                + item[
                    "motion"
                ] * 0.28
            ),
            reverse=True,
        )

        descriptions = []

        for item in ranked:

            description = item[
                "description"
            ]

            if (
                description
                and description
                not in descriptions
            ):
                descriptions.append(
                    description
                )

            if len(
                descriptions
            ) >= 3:
                break

        events.append(
            {
                "phase": phase,
                "descriptions":
                    descriptions,
                "start_beat":
                    group[
                        0
                    ][
                        "beat"
                    ],
                "end_beat":
                    group[
                        -1
                    ][
                        "beat"
                    ],
            }
        )

    return events


############################################################
# LOCAL STORY GENERATOR
############################################################

def generate_story_locally_v13(
    events,
):
    """
    Deterministic fallback.

    This is intentionally story language rather than
    cinematography language.
    """

    phase_data = {
        event[
            "phase"
        ]: event
        for event
        in events
    }

    hook = (
        "They thought this meeting would be simple. "
        "They were wrong."
    )

    setup = (
        "While they try to understand each other, "
        "the technology around them begins waking up."
    )

    complication = (
        "At first it is only a warning, but the machines "
        "keep moving and the city starts turning against them."
    )

    escalation = (
        "Then the threat becomes impossible to ignore. "
        "Something much larger is coming, and every second "
        "leaves them with fewer places to escape."
    )

    payoff = (
        "When the real machine finally appears, the choice "
        "is gone. They can fight, or they can run."
    )

    ########################################################
    # Adjust wording only when corresponding phases exist.
    ########################################################

    pieces = []

    if "HOOK" in phase_data:
        pieces.append(
            hook
        )

    if "SETUP" in phase_data:
        pieces.append(
            setup
        )

    if "COMPLICATION" in phase_data:
        pieces.append(
            complication
        )

    if "ESCALATION" in phase_data:
        pieces.append(
            escalation
        )

    if "PAYOFF" in phase_data:
        pieces.append(
            payoff
        )

    return " ".join(
        pieces
    )


############################################################
# OPTIONAL OLLAMA STORY REWRITE
############################################################

def rewrite_story_with_ollama_v13(
    events,
    fallback,
):
    """
    Use the already-local Ollama installation when available.

    If Ollama is unavailable, malformed, slow, or returns weak
    narration, V13 automatically retains the deterministic
    story.
    """

    import json
    import urllib.request

    evidence_lines = []

    for event in events:

        evidence_lines.append(
            (
                event[
                    "phase"
                ]
                + ": "
                + "; ".join(
                    event[
                        "descriptions"
                    ]
                )
            )
        )

        prompt = """
    You are the narrative editor for a short vertical science-fiction story.

    Your task is to transform the supplied visual evidence into compelling
    spoken narration WITHOUT inventing unsupported story facts.

    The visual evidence is authoritative.

    The baseline story is only a writing aid. If the baseline story contains
    a claim that is not supported by the visual evidence, discard that claim.

    STRICT EVIDENCE RULES:

    - Every factual claim must be supported by supplied visual evidence.
    - Do not invent names.
    - Do not invent relationships.
    - Do not invent motives or intentions.
    - Do not invent dialogue.
    - Do not invent warnings.
    - Do not invent destinations.
    - Do not invent causes.
    - Do not invent consequences.
    - Do not invent outcomes.
    - Do not invent actions that are not supported by the evidence.
    - Do not turn ambiguity into certainty.

    For example:

    If the evidence says:
    "character noticing something is wrong"

    you may say:
    "Something catches their attention."

    You may NOT automatically say:
    "They see the warning."

    If the evidence says:
    "characters during science fiction action"

    you may say:
    "The danger escalates around them."

    You may NOT automatically say:
    "They run for their lives."

    If the evidence says:
    "wide futuristic environment becoming threatening"

    you may say:
    "The environment becomes more threatening."

    You may NOT automatically say:
    "The city closes in around them."

    When evidence is uncertain, prefer conservative concrete wording.

    STORY STRUCTURE:

    HOOK -> SETUP -> COMPLICATION -> ESCALATION -> PAYOFF

    The hook must create immediate curiosity using supported evidence.

    The setup establishes the situation.

    The complication introduces a meaningful change.

    The escalation increases danger or tension using only supported events.

    The payoff ends on the strongest supported development.

    WRITING RULES:

    - Target 72 to 94 words.
    - Present tense.
    - Short natural spoken sentences.
    - Strong first sentence.
    - Concrete nouns and verbs.
    - Avoid filler.
    - Avoid generic hype.
    - Avoid redundant sentences.
    - Maintain clear cause-and-effect only where evidence supports it.
    - Make each sentence advance the story.
    - Sound like a human storyteller.

    NEVER mention:

    - shots
    - footage
    - editing
    - camera work
    - close-ups
    - wide shots
    - visual beats
    - filmmaking
    - the fact that this is a video

    Do not say "the sequence works".
    Do not say "watch this".
    Do not use a call to action.
    Do not end with an explanation or moral.

    FINAL GROUNDING CHECK:

    Before returning the narration, examine every factual claim.

    Ask:

    "What supplied evidence supports this exact claim?"

    If no supplied evidence clearly supports it, weaken or remove the claim.

    Then check whether you invented any:

    - action
    - motive
    - relationship
    - warning
    - cause
    - consequence
    - destination
    - outcome

    Remove anything unsupported.

    VISUAL EVIDENCE:
    """ + "\n".join(
            evidence_lines
        ) + """

    BASELINE STORY:
    """ + fallback + """

    Return ONLY the final narration.
    """

    payload = json.dumps(
        {
            "model": "qwen2.5:7b",
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.18,
                "top_p": 0.72,
            },
        }
    ).encode(
        "utf-8"
    )

    request = urllib.request.Request(
        "http://127.0.0.1:11434/api/generate",
        data=payload,
        headers={
            "Content-Type":
                "application/json"
        },
        method="POST",
    )

    try:

        with urllib.request.urlopen(
            request,
            timeout=45,
        ) as response:

            data = json.loads(
                response.read().decode(
                    "utf-8"
                )
            )

        candidate = str(
            data.get(
                "response",
                "",
            )
        ).strip()

        if candidate:
            return candidate

    except Exception as exc:

        print(
            "V13 OLLAMA:",
            "fallback narration used |",
            str(
                exc
            )[:120],
        )

    return fallback


############################################################
# STORY QA
############################################################

def story_qa_v13(
    narration,
):
    import re

    normalized = " ".join(
        str(
            narration
        ).split()
    )

    lower = normalized.lower()

    words = re.findall(
        r"[A-Za-z0-9']+",
        normalized,
    )

    banned = [
        phrase
        for phrase
        in V13_BANNED_META_PHRASES
        if phrase in lower
    ]

    sentences = [
        item.strip()
        for item
        in re.split(
            r"[.!?]+",
            normalized,
        )
        if item.strip()
    ]

    long_sentences = [
        sentence
        for sentence
        in sentences
        if len(
            sentence.split()
        ) > 23
    ]

    score = 1.0

    if len(
        words
    ) < V13_TARGET_WORDS_MIN:

        score -= min(
            0.25,
            (
                V13_TARGET_WORDS_MIN
                - len(
                    words
                )
            ) / 100.0,
        )

    if len(
        words
    ) > V13_TARGET_WORDS_MAX:

        score -= min(
            0.25,
            (
                len(
                    words
                )
                - V13_TARGET_WORDS_MAX
            ) / 100.0,
        )

    score -= (
        len(
            banned
        )
        * 0.16
    )

    score -= (
        len(
            long_sentences
        )
        * 0.06
    )

    score = max(
        0.0,
        min(
            1.0,
            score,
        ),
    )

    print()
    print(
        "========== V13 STORY QA =========="
    )

    print(
        "WORDS:",
        len(
            words
        ),
    )

    print(
        "SENTENCES:",
        len(
            sentences
        ),
    )

    print(
        "BANNED META PHRASES:",
        banned,
    )

    print(
        "OVERLONG SENTENCES:",
        len(
            long_sentences
        ),
    )

    print(
        "STORY QUALITY:",
        round(
            score,
            4,
        ),
    )

    return {
        "score": score,
        "words": len(
            words
        ),
        "banned": banned,
        "long_sentences":
            long_sentences,
    }


############################################################
# FINAL STORY BUILDER
############################################################

def build_narration_v13(
    optimized_moments,
):
    global V13_NARRATION
    global V13_STORY_SEGMENTS

    print()
    print(
        "========== V13 STORY-FIRST NARRATION =========="
    )

    evidence = (
        build_story_evidence_v13(
            optimized_moments
        )
    )

    events = (
        build_story_events_v13(
            evidence
        )
    )

    fallback = (
        generate_story_locally_v13(
            events
        )
    )

    candidate = (
        rewrite_story_with_ollama_v13(
            events,
            fallback,
        )
    )

    qa = story_qa_v13(
        candidate
    )

    ########################################################
    # Never allow a weak AI rewrite to make the final render
    # worse than the deterministic story.
    ########################################################

    if (
        qa[
            "banned"
        ]
        or qa[
            "score"
        ] < 0.78
    ):

        print(
            "V13 STORY RECOVERY:",
            "AI rewrite rejected; using grounded fallback."
        )

        candidate = fallback

        qa = story_qa_v13(
            candidate
        )

    if qa[
        "banned"
    ]:

        raise RuntimeError(
            "V13 narration still contains meta-editing language: "
            + str(
                qa[
                    "banned"
                ]
            )
        )

    V13_NARRATION = " ".join(
        candidate.split()
    )

    ########################################################
    # Save story events for diagnostics.
    ########################################################

    V13_STORY_SEGMENTS = events

    print()
    print(
        "FINAL V13 NARRATION:"
    )

    print(
        V13_NARRATION
    )

    print()
    print(
        "STORY EVENTS:"
    )

    for event in events:

        print(
            event[
                "phase"
            ],
            "| beats",
            (
                f"{event['start_beat']}"
                f"-{event['end_beat']}"
            ),
            "|",
            "; ".join(
                event[
                    "descriptions"
                ]
            ),
        )

    return V13_NARRATION


############################################################
# V13 â€” VISUAL / STORY STRUCTURE QA
############################################################

def visual_story_qa_v13(
    optimized_moments,
):
    print()
    print(
        "========== V13 VISUAL-STORY QA =========="
    )

    evidence = (
        build_story_evidence_v13(
            optimized_moments
        )
    )

    phases = {}

    for item in evidence:

        phases.setdefault(
            item[
                "phase"
            ],
            [],
        ).append(
            item
        )

    required = (
        "HOOK",
        "SETUP",
        "COMPLICATION",
        "ESCALATION",
        "PAYOFF",
    )

    missing = [
        phase
        for phase
        in required
        if not phases.get(
            phase
        )
    ]

    for phase in required:

        group = phases.get(
            phase,
            [],
        )

        if not group:
            continue

        avg_semantic = sum(
            item[
                "semantic"
            ]
            for item
            in group
        ) / len(
            group
        )

        avg_quality = sum(
            item[
                "quality"
            ]
            for item
            in group
        ) / len(
            group
        )

        avg_motion = sum(
            item[
                "motion"
            ]
            for item
            in group
        ) / len(
            group
        )

        print(
            phase,
            "| beats:",
            len(
                group
            ),
            "| semantic:",
            round(
                avg_semantic,
                3,
            ),
            "| quality:",
            round(
                avg_quality,
                3,
            ),
            "| motion:",
            round(
                avg_motion,
                3,
            ),
        )

    print(
        "MISSING STORY PHASES:",
        missing,
    )

    if missing:

        raise RuntimeError(
            "V13 visual story lacks phases: "
            + str(
                missing
            )
        )

    return evidence


############################################################
# V13 CAPTIONS â€” ALWAYS USE FINAL STORY
############################################################

def caption_chunks_v13():
    import re

    tokens = re.findall(
        r"[A-Za-z0-9']+|[,.!?;:]",
        V13_NARRATION,
    )

    chunks = []

    current = []

    strong_breaks = {
        ".",
        "!",
        "?",
        ";",
        ":",
    }

    pattern = (
        3,
        2,
        3,
        3,
        2,
    )

    pattern_index = 0

    for token in tokens:

        if token in strong_breaks:

            if current:

                chunks.append(
                    " ".join(
                        current
                    ).upper()
                )

                current = []

                pattern_index += 1

            continue

        if token == ",":

            if len(
                current
            ) >= 2:

                chunks.append(
                    " ".join(
                        current
                    ).upper()
                )

                current = []

                pattern_index += 1

            continue

        current.append(
            token
        )

        target = pattern[
            pattern_index
            % len(
                pattern
            )
        ]

        if len(
            current
        ) >= target:

            chunks.append(
                " ".join(
                    current
                ).upper()
            )

            current = []

            pattern_index += 1

    if current:

        chunks.append(
            " ".join(
                current
            ).upper()
        )

    ########################################################
    # Repair isolated one-word chunks.
    ########################################################

    repaired = []

    for chunk in chunks:

        if (
            len(
                chunk.split()
            ) == 1
            and repaired
            and len(
                repaired[
                    -1
                ].split()
            ) <= 2
        ):

            repaired[
                -1
            ] += (
                " "
                + chunk
            )

        else:

            repaired.append(
                chunk
            )

    return repaired


def caption_schedule_v13(
    voice_duration,
):
    chunks = (
        caption_chunks_v13()
    )

    if not chunks:

        return []

    usable = min(
        float(
            voice_duration
        ),
        TARGET_DURATION,
    )

    weights = []

    for chunk in chunks:

        words = chunk.split()

        weights.append(
            sum(
                0.72
                + min(
                    len(
                        word
                    ),
                    11,
                ) / 6.8
                for word
                in words
            )
        )

    total = max(
        float(
            sum(
                weights
            )
        ),
        1.0,
    )

    boundaries = [
        0.0
    ]

    running = 0.0

    for weight in weights:

        running += weight

        boundaries.append(
            usable
            * running
            / total
        )

    ########################################################
    # Reuse V12's real Piper WAV energy alignment.
    ########################################################

    energy_data = (
        speech_energy_v12()
    )

    aligned = [
        0.0
    ]

    for boundary in boundaries[
        1:-1
    ]:

        aligned.append(
            snap_to_speech_pause_v12(
                boundary,
                energy_data,
            )
        )

    aligned.append(
        usable
    )

    ########################################################
    # Monotonic cleanup.
    ########################################################

    cleaned = [
        0.0
    ]

    minimum = 0.20

    for boundary in aligned[
        1:
    ]:

        value = max(
            float(
                boundary
            ),
            cleaned[
                -1
            ]
            + minimum,
        )

        value = min(
            value,
            usable,
        )

        cleaned.append(
            value
        )

    cleaned[
        -1
    ] = usable

    schedule = []

    for index, chunk in enumerate(
        chunks
    ):

        if (
            index + 1
            >= len(
                cleaned
            )
        ):
            break

        start = float(
            cleaned[
                index
            ]
        )

        end = float(
            cleaned[
                index + 1
            ]
        )

        if end <= start:
            continue

        schedule.append(
            (
                start,
                end,
                chunk,
            )
        )

    return schedule



############################################################
# V12 â€” SURGICAL HOOK + ENDING REFINEMENT
############################################################


############################################################
# V14 â€” TEMPORAL / STORY CONTINUITY ENGINE
############################################################

V14_MAX_NORMAL_BACKWARD_JUMP = 18.0
V14_MAX_HOOK_BACKWARD_JUMP = 45.0
V14_MAJOR_BACKWARD_JUMP = 70.0


def timestamp_v14(
    moment,
):
    """
    Return the source timestamp represented by an editorial candidate.
    """

    if moment is None:
        return 0.0

    for key in (
        "timestamp",
        "center",
        "time",
    ):
        if key in moment:
            try:
                return float(
                    moment[
                        key
                    ]
                )
            except Exception:
                pass

    return 0.0


def continuity_penalty_v14(
    previous,
    current,
    *,
    beat_index,
):
    """
    Penalize source-time discontinuity without forcing the edit
    to become strictly chronological.

    Small backward cuts remain legal.
    Large unexplained rewinds become expensive.
    """

    if previous is None:
        return 0.0

    previous_time = timestamp_v14(
        previous
    )

    current_time = timestamp_v14(
        current
    )

    delta = (
        current_time -
        previous_time
    )

    # Forward movement is normally coherent.
    if delta >= 0.0:

        # Extremely large forward jumps can also feel disconnected.
        if delta > 100.0:
            return min(
                0.16,
                (
                    delta - 100.0
                ) / 500.0,
            )

        return 0.0

    backward = abs(
        delta
    )

    # Beat 2 receives extra protection because an aggressive
    # hook must not create an unexplained rewind immediately
    # after the viewer enters the story.
    if beat_index == 1:

        if backward <= 12.0:
            return 0.0

        if backward <= V14_MAX_HOOK_BACKWARD_JUMP:
            return (
                0.05
                + (
                    backward - 12.0
                ) * 0.003
            )

        if backward <= V14_MAJOR_BACKWARD_JUMP:
            return (
                0.18
                + (
                    backward
                    - V14_MAX_HOOK_BACKWARD_JUMP
                ) * 0.006
            )

        return min(
            1.25,
            0.45
            + (
                backward
                - V14_MAJOR_BACKWARD_JUMP
            ) * 0.008,
        )

    # Normal beats may make small editorial reversals.
    if backward <= V14_MAX_NORMAL_BACKWARD_JUMP:
        return (
            backward
            * 0.0015
        )

    if backward <= V14_MAJOR_BACKWARD_JUMP:
        return (
            0.04
            + (
                backward
                - V14_MAX_NORMAL_BACKWARD_JUMP
            ) * 0.0035
        )

    return min(
        0.90,
        0.25
        + (
            backward
            - V14_MAJOR_BACKWARD_JUMP
        ) * 0.006,
    )


def continuity_score_v14(
    previous,
    current,
    *,
    beat_index,
):
    return max(
        0.0,
        1.0
        - continuity_penalty_v14(
            previous,
            current,
            beat_index=beat_index,
        ),
    )


def repair_major_story_jumps_v14(
    candidate_pools,
    sequence,
):
    """
    Final continuity repair after the existing global editor.

    Only replaces a selected candidate when:

      1. the current transition contains a severe backward jump,
      2. a substantially more chronological candidate exists,
      3. the replacement remains editorially competitive.

    This avoids destroying the V11/V12 quality optimization merely
    to obtain perfect source chronology.
    """

    print()
    print(
        "========== V14 CONTINUITY REPAIR =========="
    )

    output = [
        dict(
            item
        )
        for item in sequence
    ]

    repairs = 0

    for beat_index in range(
        1,
        len(
            output
        ),
    ):

        previous = output[
            beat_index - 1
        ]

        current = output[
            beat_index
        ]

        previous_time = timestamp_v14(
            previous
        )

        current_time = timestamp_v14(
            current
        )

        jump = (
            current_time -
            previous_time
        )

        limit = (
            V14_MAX_HOOK_BACKWARD_JUMP
            if beat_index == 1
            else V14_MAJOR_BACKWARD_JUMP
        )

        if jump >= -limit:
            continue

        pool = candidate_pools[
            beat_index
        ]

        current_local = float(
            current.get(
                "local_score_v11",
                current.get(
                    "editorial_score_v9",
                    current.get(
                        "score",
                        0.0,
                    ),
                ),
            )
        )

        best = None
        best_score = -999.0

        for candidate in pool:

            candidate_time = timestamp_v14(
                candidate
            )

            candidate_jump = (
                candidate_time -
                previous_time
            )

            # For the immediate post-hook transition, strongly
            # prefer remaining near or after the hook's source era.
            if beat_index == 1:

                if candidate_jump < -V14_MAX_HOOK_BACKWARD_JUMP:
                    continue

            else:

                if candidate_jump < -V14_MAJOR_BACKWARD_JUMP:
                    continue

            local = float(
                candidate.get(
                    "local_score_v11",
                    candidate.get(
                        "editorial_score_v9",
                        candidate.get(
                            "score",
                            0.0,
                        ),
                    ),
                )
            )

            semantic = float(
                candidate.get(
                    "semantic",
                    0.0,
                )
            )

            render = float(
                candidate.get(
                    "render_quality_v10",
                    candidate.get(
                        "whole_quality",
                        0.0,
                    ),
                )
            )

            motion = float(
                candidate.get(
                    "motion",
                    0.0,
                )
            )

            continuity = continuity_score_v14(
                previous,
                candidate,
                beat_index=beat_index,
            )

            candidate_score = (
                local * 0.44
                + semantic * 0.16
                + render * 0.17
                + motion * 0.08
                + continuity * 0.15
            )

            # Do not rescue chronology with a catastrophically
            # weaker visual candidate.
            if (
                current_local > 0.0
                and local
                < current_local * 0.72
            ):
                continue

            if candidate_score > best_score:

                best_score = (
                    candidate_score
                )

                best = candidate

        if best is None:

            print(
                f"{beat_index + 1:02d} | "
                f"WARN KEEP | "
                f"backward: {jump:.2f}s | "
                f"no competitive continuity replacement"
            )

            continue

        old_time = current_time

        new_time = timestamp_v14(
            best
        )

        old_penalty = continuity_penalty_v14(
            previous,
            current,
            beat_index=beat_index,
        )

        new_penalty = continuity_penalty_v14(
            previous,
            best,
            beat_index=beat_index,
        )

        # Replacement must materially improve continuity.
        if new_penalty >= (
            old_penalty - 0.10
        ):
            continue

        output[
            beat_index
        ] = dict(
            best
        )

        repairs += 1

        print(
            f"{beat_index + 1:02d} | "
            f"REPAIRED | "
            f"{old_time:.2f}s -> {new_time:.2f}s | "
            f"old jump: {jump:.2f}s | "
            f"new jump: "
            f"{new_time - previous_time:.2f}s"
        )

    print()
    print(
        "V14 CONTINUITY REPAIRS:",
        repairs,
    )

    return output


def continuity_qa_v14(
    sequence,
):
    """
    Measure chronology after all editorial selection is complete.

    A severe opening rewind is a hard failure.
    Other major rewinds are reported and penalized.
    """

    print()
    print(
        "========== V14 CONTINUITY QA =========="
    )

    transitions = []

    major_backward = []

    total_backward = 0.0

    worst_backward = 0.0

    for index in range(
        1,
        len(
            sequence
        ),
    ):

        previous_time = timestamp_v14(
            sequence[
                index - 1
            ]
        )

        current_time = timestamp_v14(
            sequence[
                index
            ]
        )

        delta = (
            current_time -
            previous_time
        )

        transitions.append(
            delta
        )

        if delta < 0.0:

            backward = abs(
                delta
            )

            total_backward += (
                backward
            )

            worst_backward = max(
                worst_backward,
                backward,
            )

            if backward > V14_MAJOR_BACKWARD_JUMP:

                major_backward.append(
                    (
                        index + 1,
                        round(
                            delta,
                            2,
                        ),
                    )
                )

    opening_delta = (
        transitions[
            0
        ]
        if transitions
        else 0.0
    )

    severe_opening_rewind = (
        opening_delta
        < -V14_MAX_HOOK_BACKWARD_JUMP
    )

    print(
        "OPENING TRANSITION:",
        round(
            opening_delta,
            2,
        ),
        "sec",
    )

    print(
        "TOTAL BACKWARD TRAVEL:",
        round(
            total_backward,
            2,
        ),
        "sec",
    )

    print(
        "WORST BACKWARD JUMP:",
        round(
            worst_backward,
            2,
        ),
        "sec",
    )

    print(
        "MAJOR BACKWARD JUMPS:",
        major_backward,
    )

    print(
        "SEVERE OPENING REWIND:",
        severe_opening_rewind,
    )

    # Score is diagnostic, not a fake absolute quality metric.
    continuity_score = max(
        0.0,
        1.0
        - min(
            total_backward / 400.0,
            0.65,
        )
        - (
            len(
                major_backward
            )
            * 0.08
        ),
    )

    print(
        "V14 CONTINUITY SCORE:",
        round(
            continuity_score,
            3,
        ),
    )

    if severe_opening_rewind:

        raise RuntimeError(
            "V14 continuity QA rejected the edit: "
            "the hook immediately rewinds the story by more "
            "than 45 seconds."
        )

    return {
        "opening_transition":
            opening_delta,

        "total_backward":
            total_backward,

        "worst_backward":
            worst_backward,

        "major_backward":
            major_backward,

        "score":
            continuity_score,
    }

def refine_hook_and_ending_v12(
    pools,
    sequence,
):
    """
    V14.1 continuity-aware hook and ending selector.
    """

    print()
    print(
        "========== V14.1 CONTINUITY-AWARE HOOK / ENDING =========="
    )

    output = list(sequence)

    # ========================================================
    # HOOK
    # ========================================================

    second = output[1]
    second_time = float(second["timestamp"])

    if len(output) > 2:
        third = output[2]
    else:
        third = second

    hook_candidates = list(pools[0])

    original_hook = output[0]

    if not any(
        abs(
            float(candidate["timestamp"])
            - float(original_hook["timestamp"])
        ) < 0.01
        for candidate in hook_candidates
    ):
        hook_candidates.append(original_hook)

    scored_hooks = []

    for candidate in hook_candidates:

        timestamp = float(
            candidate["timestamp"]
        )

        render = float(
            candidate.get(
                "v11_render_score",
                0.0,
            )
        )

        semantic = float(
            candidate.get(
                "semantic",
                0.0,
            )
        )

        composition = float(
            candidate.get(
                "composition",
                0.0,
            )
        )

        motion = float(
            candidate.get(
                "motion",
                0.0,
            )
        )

        hook_margin = float(
            candidate.get(
                "hook_margin",
                0.0,
            )
        )

        similarity_next = float(
            (
                candidate["embedding"]
                @ second["embedding"]
            ).item()
        )

        similarity_third = float(
            (
                candidate["embedding"]
                @ third["embedding"]
            ).item()
        )

        repetition_penalty = max(
            0.0,
            similarity_next - 0.90,
        ) * 0.65

        opening_delta = (
            second_time - timestamp
        )

        rewind = max(
            0.0,
            -opening_delta,
        )

        forward_gap = max(
            0.0,
            opening_delta,
        )

        # Small rewinds are tolerable.
        # Large rewinds are increasingly expensive.

        if rewind <= 8.0:

            rewind_penalty = (
                rewind / 8.0
            ) * 0.015

        elif rewind <= 20.0:

            rewind_penalty = (
                0.015
                + (
                    (rewind - 8.0)
                    / 12.0
                ) * 0.08
            )

        elif rewind <= 45.0:

            rewind_penalty = (
                0.095
                + (
                    (rewind - 20.0)
                    / 25.0
                ) * 0.24
            )

        else:

            rewind_penalty = (
                0.335
                + min(
                    0.80,
                    (
                        rewind - 45.0
                    ) / 140.0,
                )
            )

        if forward_gap <= 35.0:

            forward_penalty = 0.0

        else:

            forward_penalty = min(
                0.16,
                (
                    forward_gap - 35.0
                ) / 180.0,
            )

        transition_similarity = max(
            0.0,
            min(
                1.0,
                (
                    similarity_next + 1.0
                ) / 2.0,
            ),
        )

        third_similarity = max(
            0.0,
            min(
                1.0,
                (
                    similarity_third + 1.0
                ) / 2.0,
            ),
        )

        story_bridge = (
            transition_similarity * 0.70
            + third_similarity * 0.30
        )

        visual_score = (
            render * 0.28
            + semantic * 0.18
            + composition * 0.14
            + motion * 0.18
            + hook_margin * 0.10
        )

        score = (
            visual_score
            + story_bridge * 0.12
            - repetition_penalty
            - rewind_penalty
            - forward_penalty
        )

        scored_hooks.append(
            {
                "candidate": candidate,
                "score": float(score),
                "timestamp": timestamp,
                "rewind": float(rewind),
                "opening_delta": float(opening_delta),
                "rewind_penalty": float(
                    rewind_penalty
                ),
                "story_bridge": float(
                    story_bridge
                ),
                "severe_rewind": bool(
                    rewind > 45.0
                ),
            }
        )

    safe_hooks = [
        item
        for item in scored_hooks
        if not item["severe_rewind"]
    ]

    if safe_hooks:

        best_item = max(
            safe_hooks,
            key=lambda item: item["score"],
        )

        selection_mode = "CONTINUITY SAFE"

    else:

        best_item = max(
            scored_hooks,
            key=lambda item: (
                -item["rewind"],
                item["score"],
            ),
        )

        selection_mode = (
            "MINIMUM REWIND FALLBACK"
        )

    best_hook = best_item["candidate"]

    output[0] = best_hook

    print(
        "HOOK:",
        round(
            float(best_hook["timestamp"]),
            2,
        ),
        "sec",
        "| score:",
        round(
            float(best_item["score"]),
            4,
        ),
        "| render:",
        round(
            float(
                best_hook.get(
                    "v11_render_score",
                    0.0,
                )
            ),
            3,
        ),
    )

    print(
        "HOOK MODE:",
        selection_mode,
    )

    print(
        "HOOK -> BEAT 2:",
        round(
            second_time
            - float(best_hook["timestamp"]),
            2,
        ),
        "sec",
    )

    print(
        "HOOK REWIND:",
        round(
            float(best_item["rewind"]),
            2,
        ),
        "sec",
    )

    print(
        "HOOK CONTINUITY PENALTY:",
        round(
            float(
                best_item["rewind_penalty"]
            ),
            4,
        ),
    )

    print(
        "HOOK STORY BRIDGE:",
        round(
            float(best_item["story_bridge"]),
            4,
        ),
    )

    # ========================================================
    # ENDING
    # ========================================================

    previous = output[-2]

    ########################################################
    # V15_1_ENDING_CHRONOLOGY_GUARD
    #
    # The final shot must behave like an ending, not like a
    # visually strong flashback.
    #
    # Prefer candidates at/after the previous story beat.
    # A tiny rewind is tolerated for editorial flexibility.
    ########################################################

    previous_time = float(
        previous.get(
            "timestamp",
            0.0,
        )
    )

    ENDING_REWIND_TOLERANCE = 5.0

    scored_endings = []

    for candidate in pools[-1]:

        render = float(
            candidate.get(
                "v11_render_score",
                0.0,
            )
        )

        semantic = float(
            candidate.get(
                "semantic",
                0.0,
            )
        )

        composition = float(
            candidate.get(
                "composition",
                0.0,
            )
        )

        motion = float(
            candidate.get(
                "motion",
                0.0,
            )
        )

        ending_margin = float(
            candidate.get(
                "ending_margin",
                0.0,
            )
        )

        timestamp = float(
            candidate.get(
                "timestamp",
                0.0,
            )
        )

        ending_delta = (
            timestamp
            - previous_time
        )

        rewind = max(
            0.0,
            -ending_delta,
        )

        similarity_previous = float(
            (
                candidate["embedding"]
                @ previous["embedding"]
            ).item()
        )

        repetition_penalty = max(
            0.0,
            similarity_previous - 0.91,
        ) * 0.65

        ####################################################
        # Chronology penalty.
        #
        # <= 5 sec:
        #     normal editorial tolerance
        #
        # > 5 sec:
        #     increasingly expensive
        #
        # A 62.8 sec rewind can no longer win merely because
        # the candidate has high motion.
        ####################################################

        if rewind <= ENDING_REWIND_TOLERANCE:

            chronology_penalty = 0.0

        elif rewind <= 20.0:

            chronology_penalty = (
                0.10
                + (
                    rewind
                    - ENDING_REWIND_TOLERANCE
                )
                / 15.0
                * 0.20
            )

        elif rewind <= 45.0:

            chronology_penalty = (
                0.30
                + (
                    rewind - 20.0
                )
                / 25.0
                * 0.35
            )

        else:

            chronology_penalty = (
                0.65
                + min(
                    0.75,
                    (
                        rewind - 45.0
                    )
                    / 100.0,
                )
            )

        visual_score = (
            render * 0.30
            + semantic * 0.17
            + composition * 0.14
            + motion * 0.25
            + ending_margin * 0.14
            - repetition_penalty
        )

        score = (
            visual_score
            - chronology_penalty
        )

        scored_endings.append(
            {
                "candidate": candidate,
                "score": float(score),
                "visual_score":
                    float(visual_score),
                "timestamp":
                    float(timestamp),
                "delta":
                    float(ending_delta),
                "rewind":
                    float(rewind),
                "chronology_penalty":
                    float(chronology_penalty),
                "safe":
                    bool(
                        rewind
                        <= ENDING_REWIND_TOLERANCE
                    ),
            }
        )

    if not scored_endings:

        raise RuntimeError(
            "V15.1 ending selector received "
            "no ending candidates."
        )

    ########################################################
    # HARD PREFERENCE:
    # choose among chronology-safe endings whenever one
    # exists.
    ########################################################

    safe_endings = [
        item
        for item in scored_endings
        if item["safe"]
    ]

    if safe_endings:

        best_end_item = max(
            safe_endings,
            key=lambda item:
                item["score"],
        )

        ending_selection_mode = (
            "CHRONOLOGY SAFE"
        )

    else:

        ####################################################
        # If the source pool genuinely contains no safe
        # ending, minimize rewind first and visual score
        # second.
        ####################################################

        best_end_item = max(
            scored_endings,
            key=lambda item: (
                -item["rewind"],
                item["score"],
            ),
        )

        ending_selection_mode = (
            "MINIMUM REWIND FALLBACK"
        )

    best_end = (
        best_end_item[
            "candidate"
        ]
    )

    best_end_score = float(
        best_end_item[
            "score"
        ]
    )

    output[-1] = best_end

    print(
        "ENDING MODE:",
        ending_selection_mode,
    )

    print(
        "ENDING DELTA:",
        round(
            float(
                best_end_item[
                    "delta"
                ]
            ),
            2,
        ),
        "sec",
    )

    print(
        "ENDING REWIND:",
        round(
            float(
                best_end_item[
                    "rewind"
                ]
            ),
            2,
        ),
        "sec",
    )

    print(
        "ENDING CHRONOLOGY PENALTY:",
        round(
            float(
                best_end_item[
                    "chronology_penalty"
                ]
            ),
            4,
        ),
    )

    print(
        "ENDING:",
        round(
            float(best_end["timestamp"]),
            2,
        ),
        "sec",
        "| score:",
        round(
            float(best_end_score),
            4,
        ),
        "| render:",
        round(
            float(
                best_end.get(
                    "v11_render_score",
                    0.0,
                )
            ),
            3,
        ),
    )

    return output

############################################################
# V12 â€” TITLE / SOURCE ARTIFACT PROTECTION
############################################################

def prepare_source_shot_v12(
    shot,
    *,
    beat_index: int,
):
    """
    Tears of Steel contains source-film/title material near
    frame edges in some shots.

    For the critical opening only, remove a narrow lower strip
    before vertical reframing.

    This is intentionally conservative.
    """

    if beat_index != 0:

        return shot

    trim_bottom = (
        shot.h
        * 0.055
    )

    usable_height = (
        shot.h
        - trim_bottom
    )

    if usable_height <= 0:

        return shot

    return shot.cropped(
        x1=0,
        y1=0,
        x2=shot.w,
        y2=usable_height,
    )


############################################################
# V12 â€” CAPTION SEGMENTATION
############################################################

def caption_chunks_v12():
    """
    Human-readable short subtitle phrases.

    Primary rule:
        2-3 spoken words per card.

    Strong punctuation starts a new phrase.
    """

    import re

    tokens = re.findall(
        r"[A-Za-z0-9']+|[,.!?;:]",
        NARRATION,
    )

    chunks = []

    current = []

    pattern = (
        2,
        3,
        2,
        3,
        2,
        3,
    )

    pattern_index = 0

    strong_breaks = {
        ".",
        "!",
        "?",
        ";",
        ":",
    }

    for token in tokens:

        if token in strong_breaks:

            if current:

                chunks.append(
                    " ".join(
                        current
                    ).upper()
                )

                current = []

                pattern_index += 1

            continue

        if token == ",":

            if len(
                current
            ) >= 2:

                chunks.append(
                    " ".join(
                        current
                    ).upper()
                )

                current = []

                pattern_index += 1

            continue

        current.append(
            token
        )

        target = pattern[
            pattern_index
            % len(
                pattern
            )
        ]

        if len(
            current
        ) >= target:

            chunks.append(
                " ".join(
                    current
                ).upper()
            )

            current = []

            pattern_index += 1

    if current:

        chunks.append(
            " ".join(
                current
            ).upper()
        )

    ########################################################
    # Avoid orphan one-word cards where possible.
    ########################################################

    repaired = []

    for chunk in chunks:

        words = chunk.split()

        if (
            len(words) == 1
            and repaired
            and len(
                repaired[
                    -1
                ].split()
            ) <= 2
        ):

            repaired[
                -1
            ] = (
                repaired[
                    -1
                ]
                + " "
                + chunk
            )

        else:

            repaired.append(
                chunk
            )

    return repaired


############################################################
# V12 â€” AUDIO-ENERGY SPEECH ALIGNMENT
############################################################

def speech_energy_v12():
    """
    Read the generated Piper WAV and produce a low-cost
    speech-energy curve.

    This allows subtitle boundaries to move toward natural
    speech pauses without adding Whisper or another model.
    """

    import wave

    if not VOICE_OUTPUT.is_file():

        return None

    try:

        with wave.open(
            str(
                VOICE_OUTPUT
            ),
            "rb",
        ) as wav:

            sample_rate = wav.getframerate()

            channels = wav.getnchannels()

            width = wav.getsampwidth()

            frames = wav.getnframes()

            raw = wav.readframes(
                frames
            )

    except Exception:

        return None

    if width != 2:

        return None

    samples = np.frombuffer(
        raw,
        dtype=np.int16,
    ).astype(
        np.float32
    )

    if channels > 1:

        samples = samples.reshape(
            -1,
            channels,
        ).mean(
            axis=1
        )

    samples /= 32768.0

    if len(
        samples
    ) == 0:

        return None

    window_seconds = 0.025

    window = max(
        1,
        int(
            sample_rate
            * window_seconds
        ),
    )

    energies = []

    times = []

    for start in range(
        0,
        len(samples),
        window,
    ):

        block = samples[
            start:
            start + window
        ]

        if len(
            block
        ) == 0:

            continue

        energy = float(
            np.mean(
                np.abs(
                    block
                )
            )
        )

        energies.append(
            energy
        )

        times.append(
            start
            / sample_rate
        )

    return (
        np.array(
            times,
            dtype=np.float32,
        ),
        np.array(
            energies,
            dtype=np.float32,
        ),
    )


def snap_to_speech_pause_v12(
    target_time,
    energy_data,
):
    """
    Move an estimated caption boundary toward the quietest
    local speech point.

    Maximum adjustment is small to protect synchronization.
    """

    if energy_data is None:

        return float(
            target_time
        )

    times, energy = energy_data

    if len(
        times
    ) == 0:

        return float(
            target_time
        )

    search_radius = 0.16

    mask = (
        times
        >= target_time
        - search_radius
    ) & (
        times
        <= target_time
        + search_radius
    )

    indexes = np.where(
        mask
    )[0]

    if len(
        indexes
    ) == 0:

        return float(
            target_time
        )

    best_index = indexes[
        int(
            np.argmin(
                energy[
                    indexes
                ]
            )
        )
    ]

    snapped = float(
        times[
            best_index
        ]
    )

    ########################################################
    # Do not over-correct.
    ########################################################

    if abs(
        snapped
        - target_time
    ) > search_radius:

        return float(
            target_time
        )

    return snapped


def caption_schedule_v12(
    voice_duration,
):
    """
    Phrase timing:
        text-length estimate
        +
        real Piper WAV pause detection
    """

    chunks = (
        caption_chunks_v12()
    )

    if not chunks:

        return []

    usable = min(
        float(
            voice_duration
        ),
        TARGET_DURATION,
    )

    weights = []

    for chunk in chunks:

        words = chunk.split()

        weight = sum(
            0.75
            + min(
                len(word),
                11,
            )
            / 6.7
            for word
            in words
        )

        weights.append(
            float(
                weight
            )
        )

    total = max(
        sum(
            weights
        ),
        1.0,
    )

    boundaries = [
        0.0
    ]

    running = 0.0

    for weight in weights:

        running += weight

        boundaries.append(
            usable
            * running
            / total
        )

    energy_data = (
        speech_energy_v12()
    )

    adjusted = [
        0.0
    ]

    for boundary in boundaries[
        1:-1
    ]:

        adjusted.append(
            snap_to_speech_pause_v12(
                boundary,
                energy_data,
            )
        )

    adjusted.append(
        usable
    )

    ########################################################
    # Enforce monotonic boundaries and minimum display time.
    ########################################################

    minimum_duration = 0.22

    cleaned = [
        0.0
    ]

    for boundary in adjusted[
        1:
    ]:

        boundary = max(
            boundary,
            cleaned[
                -1
            ]
            + minimum_duration,
        )

        boundary = min(
            boundary,
            usable,
        )

        cleaned.append(
            boundary
        )

    cleaned[
        -1
    ] = usable

    schedule = []

    for index, chunk in enumerate(
        chunks
    ):

        if (
            index + 1
            >= len(
                cleaned
            )
        ):

            break

        start = float(
            cleaned[
                index
            ]
        )

        end = float(
            cleaned[
                index + 1
            ]
        )

        if end <= start:

            continue

        schedule.append(
            (
                start,
                end,
                chunk,
            )
        )

    return schedule


############################################################
# V12 â€” PRESENTATION QA
############################################################

def final_presentation_qa_v12(
    moments,
):
    """
    Presentation-oriented diagnostics.

    Does not re-reject the complete edit for minor score
    imperfections.
    """

    print()
    print(
        "========== V12 PRESENTATION QA =========="
    )

    hook = moments[
        0
    ]

    ending = moments[
        -1
    ]

    hook_score = (
        float(
            hook.get(
                "v11_render_score",
                0.0,
            )
        ) * 0.42

        + float(
            hook.get(
                "motion",
                0.0,
            )
        ) * 0.28

        + float(
            hook.get(
                "semantic",
                0.0,
            )
        ) * 0.18

        + float(
            hook.get(
                "composition",
                0.0,
            )
        ) * 0.12
    )

    end_score = (
        float(
            ending.get(
                "v11_render_score",
                0.0,
            )
        ) * 0.38

        + float(
            ending.get(
                "motion",
                0.0,
            )
        ) * 0.34

        + float(
            ending.get(
                "semantic",
                0.0,
            )
        ) * 0.16

        + float(
            ending.get(
                "composition",
                0.0,
            )
        ) * 0.12
    )

    timestamps = [
        float(
            item[
                "timestamp"
            ]
        )
        for item
        in moments
    ]

    backwards = []

    for index in range(
        1,
        len(
            timestamps
        ) - 1,
    ):

        jump = (
            timestamps[
                index
            ]
            - timestamps[
                index - 1
            ]
        )

        if jump < -8.0:

            backwards.append(
                (
                    index + 1,
                    round(
                        jump,
                        2,
                    ),
                )
            )

    print(
        "HOOK PRESENTATION SCORE:",
        round(
            hook_score,
            4,
        ),
    )

    print(
        "ENDING PRESENTATION SCORE:",
        round(
            end_score,
            4,
        ),
    )

    print(
        "BACKWARD STORY JUMPS:",
        backwards,
    )

    print(
        "CAPTION SYSTEM:",
        "PUNCTUATION + SPEECH-PAUSE ALIGNED",
    )

    print(
        "SOURCE ARTIFACT PROTECTION:",
        "ENABLED FOR HOOK",
    )

    return {
        "hook": hook_score,
        "ending": end_score,
        "backward_jumps": (
            backwards
        ),
    }



def crop_vertical(
    clip,
    focus_ratio,
):

    scale = max(
        WIDTH / clip.w,
        HEIGHT / clip.h,
    )

    clip = clip.resized(
        scale
    )

    desired_x = (
        clip.w
        * focus_ratio
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

    return clip.cropped(
        x_center=desired_x,
        y_center=clip.h / 2,
        width=WIDTH,
        height=HEIGHT,
    )



############################################################
# V15 â€” STORY / VIEWER CONTRACT ENGINE
############################################################

V15_PIPELINE_WIRING_INSTALLED = True


def build_source_event_graph_v15(
    moments,
):
    graph = []

    total = len(moments)

    for index, moment in enumerate(moments):

        if index == 0:
            phase = "HOOK"

        elif index < max(
            2,
            int(total * 0.25),
        ):
            phase = "SETUP"

        elif index < max(
            3,
            int(total * 0.50),
        ):
            phase = "COMPLICATION"

        elif index < max(
            4,
            int(total * 0.82),
        ):
            phase = "ESCALATION"

        else:
            phase = "PAYOFF"

        description = (
            VISUAL_BEATS[index]
            if index < len(VISUAL_BEATS)
            else "science fiction action"
        )

        graph.append(
            {
                "beat": index + 1,
                "phase": phase,
                "description": description,
                "timestamp": float(
                    moment.get(
                        "timestamp",
                        0.0,
                    )
                ),
                "semantic": float(
                    moment.get(
                        "semantic",
                        0.0,
                    )
                ),
                "motion": float(
                    moment.get(
                        "motion",
                        0.0,
                    )
                ),
                "render": float(
                    moment.get(
                        "v11_render_score",
                        moment.get(
                            "whole_quality",
                            0.0,
                        ),
                    )
                ),
            }
        )

    return graph


def sequence_continuity_score_v15(
    graph,
):
    if len(graph) < 2:
        return 1.0, []

    backward = []
    penalty = 0.0

    for index in range(
        1,
        len(graph),
    ):
        delta = (
            graph[index]["timestamp"]
            - graph[index - 1]["timestamp"]
        )

        if delta < 0.0:

            magnitude = abs(delta)

            penalty += min(
                0.18,
                magnitude / 500.0,
            )

            if magnitude > 45.0:
                backward.append(
                    (
                        index + 1,
                        round(
                            delta,
                            2,
                        ),
                    )
                )

    return (
        max(
            0.0,
            1.0 - penalty,
        ),
        backward,
    )


def hook_contract_v15(
    graph,
):
    if not graph:
        return {
            "score": 0.0,
            "safe": False,
            "opening_delta": 0.0,
        }

    hook = graph[0]

    if len(graph) > 1:
        opening_delta = (
            graph[1]["timestamp"]
            - hook["timestamp"]
        )
    else:
        opening_delta = 0.0

    safe = (
        opening_delta >= -45.0
    )

    score = (
        hook["render"] * 0.35
        + hook["motion"] * 0.30
        + hook["semantic"] * 0.20
        + (
            0.15
            if safe
            else 0.0
        )
    )

    return {
        "score": max(
            0.0,
            min(
                1.0,
                score,
            ),
        ),
        "safe": safe,
        "opening_delta":
            opening_delta,
    }


def payoff_contract_v15(
    graph,
):
    if not graph:
        return {
            "score": 0.0,
        }

    ending = graph[-1]

    score = (
        ending["render"] * 0.36
        + ending["motion"] * 0.34
        + ending["semantic"] * 0.20
        + 0.10
    )

    return {
        "score": max(
            0.0,
            min(
                1.0,
                score,
            ),
        )
    }


def claim_evidence_contract_v15(
    narration,
    graph,
):
    import re

    text = " ".join(
        str(narration).split()
    )

    lower = text.lower()

    dangerous_claims = (
        "nowhere left to hide",
        "running was the only choice",
        "they knew",
        "they thought",
        "they realized",
        "they planned",
        "they wanted",
        "they decided",
        "too late",
        "had no choice",
    )

    unsupported = [
        phrase
        for phrase in dangerous_claims
        if phrase in lower
    ]

    visual_text = " ".join(
        node["description"]
        for node in graph
    ).lower()

    evidence_words = set(
        re.findall(
            r"[a-z]+",
            visual_text,
        )
    )

    narration_words = set(
        re.findall(
            r"[a-z]+",
            lower,
        )
    )

    useful = {
        word
        for word in evidence_words
        if len(word) >= 5
    }

    if useful:

        overlap = len(
            useful
            & narration_words
        )

        lexical_support = min(
            1.0,
            0.55
            + overlap
            / max(
                len(useful),
                1,
            ),
        )

    else:
        lexical_support = 1.0

    score = max(
        0.0,
        min(
            1.0,
            lexical_support
            - len(unsupported) * 0.12,
        ),
    )

    return {
        "score": score,
        "unsupported":
            unsupported,
    }


def repair_unsupported_story_v15(
    narration,
):
    text = " ".join(
        str(narration).split()
    )

    replacements = (
        (
            "there was nowhere left to hide",
            "the danger keeps growing",
        ),
        (
            "There was nowhere left to hide",
            "The danger keeps growing",
        ),
        (
            "running was the only choice",
            "the machines keep moving closer",
        ),
        (
            "Running was the only choice",
            "The machines keep moving closer",
        ),
    )

    for old, new in replacements:
        text = text.replace(
            old,
            new,
        )

    return text


def narration_visual_alignment_v15(
    narration,
    graph,
):
    import re

    narration_words = set(
        re.findall(
            r"[a-z]+",
            str(narration).lower(),
        )
    )

    phases = (
        "HOOK",
        "SETUP",
        "COMPLICATION",
        "ESCALATION",
        "PAYOFF",
    )

    phase_scores = {}

    for phase in phases:

        descriptions = " ".join(
            node["description"]
            for node in graph
            if node["phase"] == phase
        ).lower()

        words = {
            word
            for word in re.findall(
                r"[a-z]+",
                descriptions,
            )
            if len(word) > 4
        }

        if not words:
            score = 1.0

        else:
            overlap = len(
                words
                & narration_words
            )

            score = min(
                1.0,
                0.50
                + overlap
                / max(
                    len(words),
                    1,
                ),
            )

        phase_scores[phase] = score

    average = (
        sum(
            phase_scores.values()
        )
        / len(
            phase_scores
        )
    )

    return average, phase_scores


def caption_grammar_qa_v15(
    narration,
):
    import re

    text = " ".join(
        str(narration).split()
    )

    sentences = [
        sentence.strip()
        for sentence in re.split(
            r"(?<=[.!?])\s+",
            text,
        )
        if sentence.strip()
    ]

    overlong = []

    for index, sentence in enumerate(
        sentences
    ):

        words = len(
            sentence.split()
        )

        if words > 18:
            overlong.append(
                (
                    index + 1,
                    words,
                )
            )

    dangling = bool(
        re.search(
            r"\b(and|but|because|with|to|the)$",
            text.lower(),
        )
    )

    score = 1.0

    score -= (
        len(overlong) * 0.06
    )

    if dangling:
        score -= 0.15

    return {
        "score": max(
            0.0,
            score,
        ),
        "overlong":
            overlong,
        "dangling":
            dangling,
    }


def enforce_story_contract_v15(
    narration,
    moments,
):
    graph = (
        build_source_event_graph_v15(
            moments
        )
    )

    original = " ".join(
        str(narration).split()
    )

    before = (
        claim_evidence_contract_v15(
            original,
            graph,
        )
    )

    repaired = (
        repair_unsupported_story_v15(
            original
        )
    )

    after = (
        claim_evidence_contract_v15(
            repaired,
            graph,
        )
    )

    if (
        after["score"]
        >= before["score"]
    ):
        final_story = repaired
    else:
        final_story = original

    print()
    print(
        "========== V15 STORY CONTRACT =========="
    )

    print(
        "BEFORE:",
        round(
            before["score"],
            4,
        ),
        "| unsupported:",
        before["unsupported"],
    )

    print(
        "AFTER:",
        round(
            after["score"],
            4,
        ),
        "| unsupported:",
        after["unsupported"],
    )

    print()
    print(
        "FINAL V15 NARRATION:"
    )
    print(
        final_story
    )

    return final_story


def final_viewer_qa_v15(
    moments,
    narration,
):
    print()
    print(
        "========== V15 FINAL VIEWER QA =========="
    )

    graph = (
        build_source_event_graph_v15(
            moments
        )
    )

    continuity, severe = (
        sequence_continuity_score_v15(
            graph
        )
    )

    hook = hook_contract_v15(
        graph
    )

    payoff = payoff_contract_v15(
        graph
    )

    claims = (
        claim_evidence_contract_v15(
            narration,
            graph,
        )
    )

    alignment, phases = (
        narration_visual_alignment_v15(
            narration,
            graph,
        )
    )

    captions = (
        caption_grammar_qa_v15(
            narration
        )
    )

    average_render = sum(
        node["render"]
        for node in graph
    ) / max(
        len(graph),
        1,
    )

    average_semantic = sum(
        node["semantic"]
        for node in graph
    ) / max(
        len(graph),
        1,
    )

    average_motion = sum(
        node["motion"]
        for node in graph
    ) / max(
        len(graph),
        1,
    )

    viewer_score = (
        average_render * 0.16
        + average_semantic * 0.10
        + average_motion * 0.08
        + continuity * 0.18
        + hook["score"] * 0.13
        + payoff["score"] * 0.12
        + claims["score"] * 0.11
        + alignment * 0.07
        + captions["score"] * 0.05
    )

    presentation = min(
        10.0,
        max(
            0.0,
            4.0
            + viewer_score * 7.0,
        ),
    )

    print(
        "AVG RENDER:",
        round(
            average_render,
            4,
        )
    )

    print(
        "AVG SEMANTIC:",
        round(
            average_semantic,
            4,
        )
    )

    print(
        "AVG MOTION:",
        round(
            average_motion,
            4,
        )
    )

    print(
        "CONTINUITY:",
        round(
            continuity,
            4,
        )
    )

    print(
        "HOOK CONTRACT:",
        round(
            hook["score"],
            4,
        ),
        "| opening delta:",
        round(
            hook["opening_delta"],
            2,
        ),
        "sec",
    )

    print(
        "PAYOFF CONTRACT:",
        round(
            payoff["score"],
            4,
        )
    )

    print(
        "CLAIM SUPPORT:",
        round(
            claims["score"],
            4,
        )
    )

    print(
        "UNSUPPORTED CLAIMS:",
        claims["unsupported"],
    )

    print(
        "NARRATION / VISUAL:",
        round(
            alignment,
            4,
        )
    )

    print(
        "PHASE ALIGNMENT:",
        {
            key: round(
                value,
                3,
            )
            for key, value
            in phases.items()
        },
    )

    print(
        "CAPTION GRAMMAR:",
        round(
            captions["score"],
            4,
        )
    )

    print(
        "V15 VIEWER SCORE:",
        round(
            presentation,
            2,
        ),
        "/ 10",
    )

    failures = []

    if not hook["safe"]:
        failures.append(
            "unsafe opening chronology"
        )

    if severe:
        failures.append(
            "major temporal rewind"
        )

    if claims["unsupported"]:
        failures.append(
            "unsupported narration claims"
        )

    if claims["score"] < 0.58:
        failures.append(
            "weak claim grounding"
        )

    if alignment < 0.50:
        failures.append(
            "weak narration/visual alignment"
        )

    if captions["score"] < 0.70:
        failures.append(
            "caption grammar"
        )

    if failures:

        print(
            "V15 HARD FAILURES:",
            failures,
        )

        return {
            "passed": False,
            "score": presentation,
            "failures": failures,
        }

    print(
        "V15 VIEWER GATE: PASS"
    )

    return {
        "passed": True,
        "score": presentation,
        "failures": [],
    }


def build_voice(
    config,
    narration=None,
):

    if narration is None:
        narration = V13_NARRATION

    VOICE_OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    executable = Path(
        config.piper_executable
    )

    model = Path(
        config.piper_model_path
    )

    if (
        not executable.exists()
        or not model.exists()
    ):

        print(
            "VOICE: Piper unavailable; "
            "rendering without narration."
        )

        return None

    print()
    print("========== GENERATING NARRATION ==========")

    result = subprocess.run(
        [
            str(executable),
            "--model",
            str(model),
            "--output_file",
            str(VOICE_OUTPUT),
        ],
        input=narration,
        text=True,
        capture_output=True,
    )

    if result.returncode != 0:

        print(
            "VOICE GENERATION FAILED:",
            result.stderr,
        )

        return None

    if not VOICE_OUTPUT.exists():

        return None

    audio = AudioFileClip(
        str(
            VOICE_OUTPUT
        )
    )

    # Fit narration to the benchmark duration.
    if audio.duration > TARGET_DURATION:

        speed = (
            audio.duration
            / TARGET_DURATION
        )

        audio = audio.with_speed_scaled(
            speed
        )

    if audio.duration > TARGET_DURATION:

        audio = audio.subclipped(
            0,
            TARGET_DURATION,
        )

    return audio




############################################################
# V18 FINAL MASTER — LAST BENCHMARK EDITORIAL CONTROL
############################################################

V18_FINAL_MASTER = True

V18_TARGET_VIEWER_SCORE = 9.50

V18_MIN_SEMANTIC = 0.165
V18_TARGET_SEMANTIC = 0.220
V18_MIN_RENDER = 0.470
V18_TARGET_RENDER = 0.555

V18_HOOK_MIN_MOTION = 0.18
V18_PAYOFF_MIN_MOTION = 0.60

V18_MAX_DUPLICATE = 0.915
V18_MAX_MAJOR_BACKWARD_JUMPS = 0


def _v18_number(moment, *keys, default=0.0):

    for key in keys:

        try:
            if key in moment:
                return float(moment[key])
        except Exception:
            pass

    return float(default)


def _v18_mean(values):

    values = [
        float(v)
        for v in values
    ]

    if not values:
        return 0.0

    return sum(values) / len(values)


def _v18_phase_ranges(count):

    # Same narrative architecture used by V13:
    # 3 hook / 5 setup / 4 complication / 6 escalation / rest payoff.

    if count >= 22:

        return {
            "HOOK": (0, 3),
            "SETUP": (3, 8),
            "COMPLICATION": (8, 12),
            "ESCALATION": (12, 18),
            "PAYOFF": (18, count),
        }

    # Defensive proportional fallback.

    cuts = [
        0,
        max(1, round(count * 0.14)),
        max(2, round(count * 0.36)),
        max(3, round(count * 0.55)),
        max(4, round(count * 0.82)),
        count,
    ]

    return {
        "HOOK": (cuts[0], cuts[1]),
        "SETUP": (cuts[1], cuts[2]),
        "COMPLICATION": (cuts[2], cuts[3]),
        "ESCALATION": (cuts[3], cuts[4]),
        "PAYOFF": (cuts[4], cuts[5]),
    }


def final_master_qa_v18(
    moments,
    narration,
    v15_result=None,
):
    """
    Final benchmark gate.

    V18 deliberately does NOT destroy the chronology-safe V14/V15
    architecture. It audits the final sequence as a viewer would:

        hook
        visual quality
        semantic relevance
        pacing / motion
        chronology
        story progression
        payoff
        narration grounding
        captions

    It is intentionally stricter than the previous diagnostic QA,
    while avoiding arbitrary rejection caused by one borderline shot.
    """

    print()
    print(
        "========== V18 FINAL MASTER QA =========="
    )

    if not moments:

        raise RuntimeError(
            "V18: no optimized moments."
        )

    render_scores = []
    semantic_scores = []
    motion_scores = []
    timestamps = []

    weak_render = []
    weak_semantic = []

    for index, moment in enumerate(moments):

        render = _v18_number(
            moment,
            "render_score_v10",
            "render_score",
            "render",
            default=0.50,
        )

        semantic = _v18_number(
            moment,
            "semantic",
            "semantic_score",
            "semantic_v9",
            default=0.20,
        )

        motion = _v18_number(
            moment,
            "motion",
            "motion_score",
            default=0.40,
        )

        timestamp = _v18_number(
            moment,
            "timestamp",
            "center",
            "time",
            default=0.0,
        )

        render_scores.append(render)
        semantic_scores.append(semantic)
        motion_scores.append(motion)
        timestamps.append(timestamp)

        if render < V18_MIN_RENDER:
            weak_render.append(index + 1)

        if semantic < V18_MIN_SEMANTIC:
            weak_semantic.append(index + 1)

    avg_render = _v18_mean(render_scores)
    avg_semantic = _v18_mean(semantic_scores)
    avg_motion = _v18_mean(motion_scores)

    phases = _v18_phase_ranges(
        len(moments)
    )

    phase_metrics = {}

    for phase, (start, end) in phases.items():

        phase_metrics[phase] = {
            "semantic": _v18_mean(
                semantic_scores[start:end]
            ),
            "render": _v18_mean(
                render_scores[start:end]
            ),
            "motion": _v18_mean(
                motion_scores[start:end]
            ),
        }

    hook = phase_metrics["HOOK"]
    payoff = phase_metrics["PAYOFF"]

    backward_jumps = []

    for i in range(
        1,
        len(timestamps),
    ):

        delta = (
            timestamps[i]
            - timestamps[i - 1]
        )

        if delta < -18.0:

            backward_jumps.append(
                (
                    i,
                    i + 1,
                    round(delta, 2),
                )
            )

    narration_words = re.findall(
        r"[A-Za-z0-9']+",
        narration or "",
    )

    narration_length_score = max(
        0.0,
        1.0
        - abs(
            len(narration_words) - 78
        ) / 78.0,
    )

    # Story progression:
    # motion should generally rise toward escalation/payoff.

    progression = (
        phase_metrics["ESCALATION"]["motion"]
        + phase_metrics["PAYOFF"]["motion"]
    ) / 2.0

    progression_score = min(
        1.0,
        max(
            0.0,
            progression / 0.72,
        ),
    )

    semantic_score = min(
        1.0,
        avg_semantic / 0.235,
    )

    render_score = min(
        1.0,
        avg_render / 0.585,
    )

    motion_score = min(
        1.0,
        avg_motion / 0.62,
    )

    hook_score = min(
        1.0,
        (
            hook["semantic"] / 0.235
            + hook["render"] / 0.57
            + hook["motion"] / 0.34
        ) / 3.0,
    )

    payoff_score = min(
        1.0,
        (
            payoff["semantic"] / 0.225
            + payoff["render"] / 0.57
            + payoff["motion"] / 0.78
        ) / 3.0,
    )

    chronology_score = (
        1.0
        if not backward_jumps
        else max(
            0.0,
            1.0
            - len(backward_jumps) * 0.20,
        )
    )

    v15_score = 0.0
    claim_support = 0.0
    narration_visual = 0.0

    if isinstance(
        v15_result,
        dict,
    ):

        try:
            v15_score = float(
                v15_result.get(
                    "score",
                    v15_result.get(
                        "viewer_score",
                        0.0,
                    ),
                )
            )
        except Exception:
            v15_score = 0.0

        try:
            claim_support = float(
                v15_result.get(
                    "claim_support",
                    0.0,
                )
            )
        except Exception:
            claim_support = 0.0

        try:
            narration_visual = float(
                v15_result.get(
                    "narration_visual",
                    v15_result.get(
                        "narration_visual_score",
                        0.0,
                    ),
                )
            )
        except Exception:
            narration_visual = 0.0

    # If V15 uses a 10-point scale, normalize it.
    if v15_score > 1.5:
        v15_normalized = min(
            1.0,
            v15_score / 10.0,
        )
    else:
        v15_normalized = min(
            1.0,
            max(
                0.0,
                v15_score,
            ),
        )

    # V18 internal benchmark estimate.
    #
    # This is NOT claimed to equal a human rating.
    # It is a deterministic pre-render quality estimate.

    composite = (
        hook_score * 0.16
        + semantic_score * 0.14
        + render_score * 0.12
        + motion_score * 0.08
        + progression_score * 0.10
        + payoff_score * 0.15
        + chronology_score * 0.10
        + narration_length_score * 0.05
        + v15_normalized * 0.10
    )

    estimated_score = round(
        composite * 10.0,
        2,
    )

    print(
        "AVG RENDER:",
        round(avg_render, 4),
    )
    print(
        "AVG SEMANTIC:",
        round(avg_semantic, 4),
    )
    print(
        "AVG MOTION:",
        round(avg_motion, 4),
    )

    print(
        "WEAK RENDER BEATS:",
        weak_render,
    )
    print(
        "WEAK SEMANTIC BEATS:",
        weak_semantic,
    )

    print(
        "HOOK:",
        {
            key: round(value, 3)
            for key, value
            in hook.items()
        },
    )

    print(
        "PAYOFF:",
        {
            key: round(value, 3)
            for key, value
            in payoff.items()
        },
    )

    print(
        "MAJOR BACKWARD JUMPS:",
        backward_jumps,
    )

    print(
        "NARRATION WORDS:",
        len(narration_words),
    )

    print(
        "V15 SCORE INPUT:",
        round(v15_score, 3),
    )

    print(
        "V18 INTERNAL BENCHMARK:",
        estimated_score,
        "/ 10",
    )

    failures = []

    # Hard failures are restricted to viewer-visible structural
    # problems. Borderline model scores alone do not kill a render.

    if len(backward_jumps) > V18_MAX_MAJOR_BACKWARD_JUMPS:

        failures.append(
            "major chronology regression"
        )

    if avg_render < 0.50:

        failures.append(
            "overall rendered-frame quality too low"
        )

    if avg_semantic < 0.185:

        failures.append(
            "overall visual relevance too low"
        )

    if len(weak_render) >= 5:

        failures.append(
            "too many weak rendered shots"
        )

    if len(weak_semantic) >= 6:

        failures.append(
            "too many weak semantic matches"
        )

    if payoff["motion"] < 0.50:

        failures.append(
            "payoff lacks visual energy"
        )

    if len(narration_words) < 55:

        failures.append(
            "narration too thin"
        )

    if len(narration_words) > 105:

        failures.append(
            "narration overcrowded"
        )

    # Preserve V15's actual evidence contract.
    if isinstance(
        v15_result,
        dict,
    ):

        if not bool(
            v15_result.get(
                "passed",
                True,
            )
        ):

            failures.append(
                "V15 evidence/viewer contract failed"
            )

    passed = not failures

    print(
        "V18 MASTER GATE:",
        "PASS"
        if passed
        else "FAIL",
    )

    if failures:

        print(
            "V18 FAILURES:",
            failures,
        )

    return {
        "passed": passed,
        "failures": failures,
        "estimated_score": estimated_score,
        "average_render": avg_render,
        "average_semantic": avg_semantic,
        "average_motion": avg_motion,
        "hook": hook,
        "payoff": payoff,
        "backward_jumps": backward_jumps,
        "claim_support": claim_support,
        "narration_visual": narration_visual,
    }



def main():
    global V13_NARRATION
    config = RuntimeConfig.from_environment()

    configure_moviepy_ffmpeg(
        config.ffmpeg_executable
    )

    if not SOURCE.is_file():

        raise FileNotFoundError(
            SOURCE
        )

    source = VideoFileClip(
        str(
            SOURCE
        )
    )

    print(
        "SOURCE:",
        SOURCE,
    )

    (
        model,
        preprocess,
        tokenizer,
        device,
    ) = load_clip()

    scenes = detect_scenes(
        source
    )

    (
        entries,
        scene_features,
    ) = index_scenes(
        source,
        scenes,
        model,
        preprocess,
        device,
    )

    prompts = text_embeddings(
        model,
        tokenizer,
        device,
    )

    selected = choose_story(
        entries,
        scene_features,
        prompts,
    )

    candidate_pools = (
        build_candidate_pools_v8(
            source,
            entries,
            selected,
            model=model,
            preprocess=preprocess,
            tokenizer=tokenizer,
            device=device,
        )
    )

    candidate_pools = (
        upgrade_candidate_pools_v9(
            source,
            entries,
            selected,
            candidate_pools,
            scene_features,
            model=model,
            preprocess=preprocess,
            tokenizer=tokenizer,
            device=device,
        )
    )

    optimized_moments = (
        optimize_complete_sequence_v8(
            candidate_pools
        )
    )

    final_qa_v9(
        optimized_moments
    )

    optimized_moments = (
        polish_sequence_v10(
            source,
            entries,
            selected,
            candidate_pools,
            optimized_moments,
        )
    )

    v11_candidate_pools = (
        prepare_candidate_pools_v11(
            source,
            entries,
            selected,
            candidate_pools,
            optimized_moments,
        )
    )

    optimized_moments = (
        optimize_sequence_v11(
            v11_candidate_pools
        )
    )

    optimized_moments = (
        refine_hook_and_ending_v12(
            v11_candidate_pools,
            optimized_moments,
        )
    )

    optimized_moments = (
        repair_major_story_jumps_v14(
            v11_candidate_pools,
            optimized_moments,
        )
    )

    continuity_qa_v14(
        optimized_moments
    )
    final_editorial_qa_v11(
        optimized_moments
    )

    final_presentation_qa_v12(
        optimized_moments
    )

    visual_story_qa_v13(
        optimized_moments
    )

    build_narration_v13(
        optimized_moments
    )


    ########################################################
    # V15 â€” CLAIM / EVIDENCE STORY CONTRACT
    ########################################################

    V13_NARRATION = enforce_story_contract_v15(
        V13_NARRATION,
        optimized_moments,
    )



    ########################################################
    # V15 â€” FINAL PRE-RENDER VIEWER GATE
    ########################################################

    v15_viewer_result = final_viewer_qa_v15(
        optimized_moments,
        V13_NARRATION,
    )

    if not v15_viewer_result["passed"]:

        raise RuntimeError(
            "V15 viewer QA rejected the edit before encoding. "
            "Failures: "
            + str(
                v15_viewer_result[
                    "failures"
                ]
            )
        )

    ########################################################
    # V18 — FINAL MASTER PRE-ENCODE GATE
    ########################################################

    v18_master_result = final_master_qa_v18(
        optimized_moments,
        V13_NARRATION,
        v15_viewer_result,
    )

    if not v18_master_result["passed"]:

        raise RuntimeError(
            "V18 FINAL MASTER rejected the edit before encoding. "
            "Failures: "
            + str(
                v18_master_result[
                    "failures"
                ]
            )
        )

    print()
    print(
        "V18 FINAL PRE-RENDER SCORE:",
        v18_master_result[
            "estimated_score"
        ],
        "/ 10",
    )
    print(
        "TARGET:",
        V18_TARGET_VIEWER_SCORE,
        "/ 10",
    )
    print(
        "NOTE: final score still requires watching the encoded MP4."
    )
    print()

    voice = build_voice(
        config,
        narration=V13_NARRATION,
    )

    clips = []
    captions = []

    base = None
    final = None

    try:

        for index, (
            scene_index,
            duration,
        ) in enumerate(
            zip(
                selected,
                SHOT_DURATIONS,
            )
        ):

            moment = optimized_moments[
                index
            ]

            render_scene_index = int(
                moment.get(
                    "scene_index_v9",
                    scene_index,
                )
            )

            entry = entries[
                render_scene_index
            ]

            center = float(
                moment[
                    "timestamp"
                ]
            )

            start = max(
                float(
                    entry[
                        "start"
                    ]
                ),
                center
                - duration / 2,
            )

            scene_end = float(
                entry[
                    "end"
                ]
            )

            if (
                start + duration
                > scene_end
            ):

                start = max(
                    float(
                        entry[
                            "start"
                        ]
                    ),
                    scene_end
                    - duration,
                )

            end = min(
                source.duration,
                start + duration,
            )

            if (
                end - start
                <= 0.05
            ):

                raise RuntimeError(
                    "Invalid V5 shot duration "
                    f"for beat {index + 1}."
                )

            shot = source.subclipped(
                start,
                end,
            )

            shot = prepare_source_shot_v12(
                shot,
                beat_index=index,
            )

            shot = shot.with_audio(
                None
            )

            focus_track = (
                build_focus_track_v11(
                    source,
                    start=float(start),
                    end=float(end),
                )
            )

            shot = dynamic_crop_v8(
                shot,
                focus_track,
            )

            ################################################
            # Mild pace shaping:
            # later/high-energy shots get subtle speed lift.
            ################################################

            energy = ENERGY_CURVE[
                index
            ]

            # V11:
            # preserve original cinematic motion.
            speed = 1.0

            if speed > 1.001:

                shot = (
                    shot
                    .with_speed_scaled(
                        speed
                    )
                    .with_duration(
                        duration
                    )
                )

            else:

                shot = shot.with_duration(
                    duration
                )

            clips.append(
                shot
            )

        base = concatenate_videoclips(
            clips,
            method="compose",
        ).with_duration(
            TARGET_DURATION
        )

        ####################################################
        # Narration-synchronized phrase captions.
        ####################################################

        if voice is not None:

            caption_schedule = (
                caption_schedule_v13(
                    float(
                        voice.duration
                    )
                )
            )

        else:

            caption_schedule = []

        for caption_index, (
            caption_start,
            caption_end,
            caption_text,
        ) in enumerate(
            caption_schedule
        ):

            if (
                caption_end
                <= caption_start
            ):
                continue

            caption = (
                TextClip(
                    text=caption_text,
                    font=V12_FONT,
                    font_size=82,
                    color="white",
                    stroke_color="black",
                    stroke_width=7,
                    method="caption",
                    size=(
                        870,
                        None,
                    ),
                    text_align="center",
                )
                .with_start(
                    caption_start
                )
                .with_duration(
                    caption_end
                    - caption_start
                )
                .with_position(
                    (
                        "center",
                        1010,
                    )
                )
            )

            captions.append(
                caption
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
        ).with_duration(
            TARGET_DURATION
        )

        if voice is not None:

            final = final.with_audio(
                voice
            )

        OUTPUT.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        print()
        print(
            "========== RENDERING NARRATIVE V13 =========="
        )

        final.write_videofile(
            str(
                OUTPUT
            ),
            fps=FPS,
            codec="libx264",
            audio_codec="aac",
            preset="medium",
            logger=None,
        )

        print()
        print(
            "========== V13 COMPLETE =========="
        )

        print(
            "VIDEO:",
            OUTPUT,
        )

        print(
            "SCENES INDEXED:",
            len(
                entries
            ),
        )

        print(
            "SHOTS:",
            len(
                clips
            ),
        )

        print(
            "VOICE:",
            voice is not None,
        )

    finally:

        if final is not None:
            final.close()

        if base is not None:
            base.close()

        if voice is not None:
            voice.close()

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




