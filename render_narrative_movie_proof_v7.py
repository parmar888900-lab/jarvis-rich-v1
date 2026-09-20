"""Jarvis Rich V1 — narrative scene editor V7."""

from __future__ import annotations

import subprocess
from pathlib import Path

import cv2
import numpy as np
import open_clip
import torch
from PIL import Image

from moviepy import (
    AudioFileClip,
    CompositeAudioClip,
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
    "NARRATIVE_MOVIE_REFERENCE_PROOF_V7.mp4"
)

VOICE_OUTPUT = Path(
    "generated/audio/"
    "narrative_movie_v7.wav"
)

# Avoid the film's credits entirely for this benchmark.
SEARCH_START = 20.0
SEARCH_END = 580.0

# V5 ranking / QA.
LOCAL_SAMPLE_COUNT = 11

MIN_LOCAL_SEMANTIC = 0.145
MIN_LOCAL_QUALITY = 0.22

MAX_NEAR_DUPLICATE = 0.925

ENERGY_CURVE = (
    0.20, 0.22, 0.24, 0.28, 0.30, 0.34,
    0.37, 0.40, 0.43, 0.47, 0.50, 0.54,
    0.58, 0.62, 0.67, 0.72, 0.77, 0.82,
    0.87, 0.91, 0.96, 1.00,
)

SHOT_DURATIONS = [
    1.2,
    1.7,
    1.9,
    2.1,
    1.8,
    1.8,
    1.7,
    1.8,
    1.9,
    1.9,
    1.9,
    2.0,
    1.9,
    1.8,
    1.7,
    1.6,
    1.6,
    1.5,
    1.4,
    1.3,
    1.2,
    1.3,
]

NARRATION = (
    "At first this looks like a quiet reunion, but the city around them "
    "is already preparing for something worse. She watches him carefully "
    "as the technology comes alive. Then the scale changes. What seemed "
    "like a conversation becomes a survival problem. The machines move, "
    "the environment turns hostile, and every reaction suddenly matters. "
    "That is why the sequence works: it keeps jumping between faces, "
    "machinery and wide danger shots before the action completely takes over."
)

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
# V6 — SEGMENT QA
############################################################

def segment_qa(
    source,
    *,
    timestamp: float,
    scene_start: float,
    scene_end: float,
    target_duration: float,
):
    """
    Judge the WHOLE proposed shot rather than one thumbnail.

    Reject:
        - blur / darkness over multiple frames
        - poor composition
        - dead / unusable segments
    """

    start = max(
        scene_start,
        timestamp
        - target_duration / 2,
    )

    if (
        start + target_duration
        > scene_end
    ):

        start = max(
            scene_start,
            scene_end
            - target_duration,
        )

    end = min(
        scene_end,
        start + target_duration,
    )

    if (
        end - start
        < min(
            0.7,
            target_duration * 0.65,
        )
    ):
        return {
            "valid": False,
            "score": 0.0,
            "valid_ratio": 0.0,
            "composition": 0.0,
        }

    times = np.linspace(
        start,
        end,
        7,
    )

    qualities = []
    compositions = []

    valid_frames = 0

    for sample_time in times:

        frame = source.get_frame(
            float(sample_time)
        ).astype(
            np.uint8
        )

        quality = quality_score(
            frame
        )

        if quality is None:
            continue

        composition, _ = (
            composition_score(
                frame
            )
        )

        valid_frames += 1

        qualities.append(
            float(
                quality
            )
        )

        compositions.append(
            float(
                composition
            )
        )

    ratio = (
        valid_frames
        / len(times)
    )

    if not qualities:

        return {
            "valid": False,
            "score": 0.0,
            "valid_ratio": ratio,
            "composition": 0.0,
        }

    average_quality = float(
        np.mean(
            qualities
        )
    )

    average_composition = float(
        np.mean(
            compositions
        )
    )

    score = (
        average_quality
        * 0.58
        + average_composition
        * 0.42
    )

    valid = (
        ratio >= 0.72
        and score >= 0.47
    )

    return {
        "valid": valid,
        "score": score,
        "valid_ratio": ratio,
        "composition": average_composition,
    }


############################################################
# V6 — LOCAL OPTIMIZER WITH REPLACEMENT
############################################################

def optimize_selected_moments_v6(
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
    V6:
    scene selection -> candidate moments -> whole-shot QA.

    A high CLIP score can no longer automatically win.
    """

    print()
    print(
        "========== V6 SHOT QA + REPLACEMENT =========="
    )

    output = []

    recent_embeddings = []

    rejected_count = 0

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

        if beat_index == 0:

            candidates = rerank_hook_v7(
                candidates
            )

        if not candidates:

            raise RuntimeError(
                "No candidates for V6 beat "
                f"{beat_index + 1}."
            )

        winner = None
        winner_qa = None

        for candidate in candidates:

            if (
                candidate[
                    "quality"
                ]
                < MIN_LOCAL_QUALITY
            ):
                rejected_count += 1
                continue

            ################################################
            # Duplicate check against the last 5 shots.
            ################################################

            duplicate = False

            for previous_embedding in (
                recent_embeddings
            ):

                similarity = float(
                    (
                        candidate[
                            "embedding"
                        ]
                        @ previous_embedding
                    ).item()
                )

                if (
                    similarity
                    >= MAX_NEAR_DUPLICATE
                ):

                    duplicate = True
                    break

            if duplicate:

                rejected_count += 1
                continue

            ################################################
            # WHOLE SHOT validation.
            ################################################

            qa = segment_qa(
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
                target_duration=float(
                    SHOT_DURATIONS[
                        beat_index
                    ]
                ),
            )

            if not qa[
                "valid"
            ]:

                rejected_count += 1
                continue

            ################################################
            # Re-rank using render-level suitability.
            ################################################

            candidate[
                "v6_final_score"
            ] = (
                candidate[
                    "score"
                ]
                * 0.72
                + qa[
                    "score"
                ]
                * 0.28
            )

            if (
                winner is None
                or candidate[
                    "v6_final_score"
                ]
                > winner[
                    "v6_final_score"
                ]
            ):

                winner = candidate
                winner_qa = qa

        ####################################################
        # If every strict candidate failed, use best available
        # rather than abort — but report it.
        ####################################################

        if winner is None:

            winner = candidates[
                0
            ]

            winner_qa = segment_qa(
                source,
                timestamp=float(
                    winner[
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
                target_duration=float(
                    SHOT_DURATIONS[
                        beat_index
                    ]
                ),
            )

            print(
                "QA FALLBACK:",
                beat_index + 1,
            )

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
            "| Q:",
            round(
                winner[
                    "quality"
                ],
                3,
            ),
            "| MOT:",
            round(
                winner[
                    "motion"
                ],
                3,
            ),
            "| SEG:",
            round(
                winner_qa[
                    "score"
                ],
                3,
            ),
            "| VALID:",
            winner_qa[
                "valid"
            ],
            "|",
            VISUAL_BEATS[
                beat_index
            ],
        )

    print()
    print(
        "V6 CANDIDATES REJECTED:",
        rejected_count,
    )

    return output


############################################################
# V6 — MULTI-FRAME SUBJECT TRACK
############################################################

def build_focus_track(
    source,
    *,
    start: float,
    end: float,
    samples: int = 9,
):
    """
    Track visual focus across a shot.

    V5:
        one focus_x for whole clip.

    V6:
        multiple keyframes + interpolation.
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
        samples,
    )

    raw_values = []

    for timestamp in times:

        frame = source.get_frame(
            float(timestamp)
        ).astype(
            np.uint8
        )

        _, focus = composition_score(
            frame
        )

        raw_values.append(
            float(
                focus
            )
        )

    ########################################################
    # Median smoothing.
    ########################################################

    smoothed = []

    for index in range(
        len(raw_values)
    ):

        left = max(
            0,
            index - 1,
        )

        right = min(
            len(raw_values),
            index + 2,
        )

        smoothed.append(
            float(
                np.median(
                    raw_values[
                        left:right
                    ]
                )
            )
        )

    ########################################################
    # Limit sudden horizontal jumps.
    ########################################################

    stable = [
        smoothed[
            0
        ]
    ]

    maximum_step = 0.10

    for value in smoothed[
        1:
    ]:

        previous = stable[
            -1
        ]

        delta = (
            value
            - previous
        )

        delta = max(
            -maximum_step,
            min(
                maximum_step,
                delta,
            ),
        )

        stable.append(
            previous
            + delta
        )

    return [
        (
            float(
                timestamp
                - start
            ),
            max(
                0.12,
                min(
                    0.88,
                    float(value),
                ),
            ),
        )
        for timestamp, value
        in zip(
            times,
            stable,
        )
    ]


def dynamic_crop_vertical(
    clip,
    focus_track,
):
    """
    Render a true moving 9:16 crop.

    Uses MoviePy transform() and OpenCV resizing.
    """

    track_times = np.array(
        [
            item[
                0
            ]
            for item in focus_track
        ],
        dtype=np.float32,
    )

    track_values = np.array(
        [
            item[
                1
            ]
            for item in focus_track
        ],
        dtype=np.float32,
    )

    def transform_frame(
        get_frame,
        t,
    ):

        frame = get_frame(
            t
        )

        frame = np.asarray(
            frame
        ).astype(
            np.uint8
        )

        original_h, original_w = (
            frame.shape[:2]
        )

        scale = max(
            WIDTH
            / original_w,
            HEIGHT
            / original_h,
        )

        resized_w = int(
            np.ceil(
                original_w
                * scale
            )
        )

        resized_h = int(
            np.ceil(
                original_h
                * scale
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

        focus = float(
            np.interp(
                float(t),
                track_times,
                track_values,
            )
        )

        desired_x = (
            resized_w
            * focus
        )

        half_width = (
            WIDTH
            / 2
        )

        desired_x = max(
            half_width,
            min(
                resized_w
                - half_width,
                desired_x,
            ),
        )

        x1 = int(
            round(
                desired_x
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

        crop = resized[
            y1:
            y1 + HEIGHT,
            x1:
            x1 + WIDTH,
        ]

        ####################################################
        # Defensive exact sizing.
        ####################################################

        if (
            crop.shape[
                0
            ]
            != HEIGHT
            or crop.shape[
                1
            ]
            != WIDTH
        ):

            crop = cv2.resize(
                crop,
                (
                    WIDTH,
                    HEIGHT,
                ),
                interpolation=(
                    cv2.INTER_LANCZOS4
                ),
            )

        return crop

    return clip.transform(
        transform_frame
    )


############################################################
# V6 — BETTER CAPTION CHUNKS
############################################################

def narration_caption_chunks_v6():
    """
    Shorter phrase groups than V5.

    Avoid giant caption blocks.
    """

    import re

    clean = re.sub(
        r"[^\w\s']",
        " ",
        NARRATION,
    )

    words = [
        word
        for word in clean.split()
        if word
    ]

    chunks = []

    index = 0

    pattern = (
        2,
        3,
        3,
        2,
        3,
    )

    pattern_index = 0

    while index < len(
        words
    ):

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


def build_synced_captions_v6(
    voice_duration: float,
):
    """
    Weighted timing based on phrase length.

    Keeps captions short and readable.
    """

    chunks = (
        narration_caption_chunks_v6()
    )

    if not chunks:
        return []

    weights = []

    for chunk in chunks:

        words = chunk.split()

        weight = sum(
            max(
                1.0,
                len(word)
                / 4.5,
            )
            for word in words
        )

        weights.append(
            weight
        )

    total_weight = max(
        sum(
            weights
        ),
        1.0,
    )

    usable_duration = min(
        float(
            voice_duration
        ),
        TARGET_DURATION,
    )

    current = 0.0

    schedule = []

    for chunk, weight in zip(
        chunks,
        weights,
    ):

        duration = (
            usable_duration
            * weight
            / total_weight
        )

        duration = max(
            0.38,
            min(
                1.25,
                duration,
            ),
        )

        end = min(
            usable_duration,
            current
            + duration,
        )

        schedule.append(
            (
                current,
                end,
                chunk,
            )
        )

        current = end

        if (
            current
            >= usable_duration
        ):
            break

    return schedule




############################################################
# V7 — STRONGER HOOK RANKING
############################################################

def rerank_hook_v7(
    candidates,
):
    """
    The first shot has a different job from normal beats:
    stop the scroll.

    Favor:
      semantic relevance
      composition
      motion
      visual quality
    """

    if not candidates:
        return candidates

    for item in candidates:

        item[
            "hook_score"
        ] = (
            item[
                "semantic"
            ] * 0.34
            + item[
                "composition"
            ] * 0.25
            + item[
                "quality"
            ] * 0.23
            + item[
                "motion"
            ] * 0.18
        )

    return sorted(
        candidates,
        key=lambda item: item[
            "hook_score"
        ],
        reverse=True,
    )


############################################################
# V7 — CAPTION PHRASES
############################################################

def caption_phrases_v7():
    """
    Short 2-3 word phrases.

    This is intentionally denser than V6's caption blocks
    and closer to modern commentary subtitles.
    """

    import re

    clean = re.sub(
        r"[^\w\s']",
        " ",
        NARRATION,
    )

    words = [
        word
        for word in clean.split()
        if word
    ]

    phrases = []

    pattern = (
        2,
        3,
        2,
        3,
        3,
        2,
    )

    cursor = 0
    pattern_index = 0

    while cursor < len(
        words
    ):

        size = pattern[
            pattern_index
            % len(pattern)
        ]

        phrase_words = words[
            cursor:
            cursor + size
        ]

        if not phrase_words:
            break

        # Longest word becomes emphasis word.
        emphasis = max(
            phrase_words,
            key=len,
        )

        phrases.append(
            {
                "text": " ".join(
                    phrase_words
                ).upper(),
                "emphasis": (
                    emphasis.upper()
                ),
                "word_count": len(
                    phrase_words
                ),
                "weight": sum(
                    max(
                        1.0,
                        len(word) / 4.4,
                    )
                    for word
                    in phrase_words
                ),
            }
        )

        cursor += size
        pattern_index += 1

    return phrases


def caption_schedule_v7(
    voice_duration: float,
):
    """
    Approximate spoken timing from word-length weights.

    This is still not forced alignment, but it is substantially
    tighter than evenly distributing captions.
    """

    phrases = caption_phrases_v7()

    if not phrases:
        return []

    usable = min(
        float(
            voice_duration
        ),
        TARGET_DURATION,
    )

    total_weight = sum(
        phrase[
            "weight"
        ]
        for phrase
        in phrases
    )

    total_weight = max(
        total_weight,
        1.0,
    )

    cursor = 0.0
    schedule = []

    for phrase in phrases:

        raw_duration = (
            usable
            * phrase[
                "weight"
            ]
            / total_weight
        )

        duration = max(
            0.32,
            min(
                1.05,
                raw_duration,
            ),
        )

        end = min(
            usable,
            cursor + duration,
        )

        if end <= cursor:
            break

        schedule.append(
            {
                "start": cursor,
                "end": end,
                "text": phrase[
                    "text"
                ],
                "emphasis": phrase[
                    "emphasis"
                ],
            }
        )

        cursor = end

        if cursor >= usable:
            break

    return schedule


############################################################
# V7 — CAPTION SAFE POSITION
############################################################

def caption_y_v7(
    source,
    optimized_moments,
    timeline_time: float,
):
    """
    Put text away from the dominant face region when possible.
    """

    elapsed = 0.0

    shot_index = 0

    for index, duration in enumerate(
        SHOT_DURATIONS
    ):

        if (
            elapsed
            <= timeline_time
            < elapsed + duration
        ):

            shot_index = index
            break

        elapsed += duration

    shot_index = min(
        shot_index,
        len(
            optimized_moments
        ) - 1,
    )

    timestamp = float(
        optimized_moments[
            shot_index
        ][
            "timestamp"
        ]
    )

    frame = source.get_frame(
        timestamp
    ).astype(
        np.uint8
    )

    faces = detect_faces(
        frame
    )

    if not faces:

        return 980

    h = frame.shape[
        0
    ]

    centers_y = [
        y + fh / 2
        for x, y, fw, fh
        in faces
    ]

    average_y = (
        float(
            np.mean(
                centers_y
            )
        )
        / h
    )

    # Face high -> caption lower.
    if average_y < 0.48:
        return 1110

    # Face low -> caption higher.
    return 760


############################################################
# V7 — SYNTHETIC IMPACT AUDIO
############################################################

def build_v7_sfx():
    """
    Generate very subtle cinematic impact pulses at major beats.

    No external copyrighted audio is needed.
    """

    import wave

    sample_rate = 44100

    duration = TARGET_DURATION

    sample_count = int(
        duration
        * sample_rate
    )

    audio = np.zeros(
        sample_count,
        dtype=np.float32,
    )

    ########################################################
    # Low ambient bed.
    ########################################################

    timeline = (
        np.arange(
            sample_count,
            dtype=np.float32,
        )
        / sample_rate
    )

    ambient = (
        np.sin(
            2
            * np.pi
            * 52.0
            * timeline
        )
        * 0.007
    )

    audio += ambient.astype(
        np.float32
    )

    ########################################################
    # Impact at selected narrative moments.
    ########################################################

    cut_times = []

    elapsed = 0.0

    for index, duration_value in enumerate(
        SHOT_DURATIONS
    ):

        if index in {
            0,
            5,
            8,
            12,
            16,
            19,
            21,
        }:

            cut_times.append(
                elapsed
            )

        elapsed += duration_value

    for hit_time in cut_times:

        start = int(
            hit_time
            * sample_rate
        )

        hit_duration = int(
            0.28
            * sample_rate
        )

        end = min(
            sample_count,
            start + hit_duration,
        )

        length = (
            end - start
        )

        if length <= 0:
            continue

        local_t = (
            np.arange(
                length,
                dtype=np.float32,
            )
            / sample_rate
        )

        envelope = np.exp(
            -local_t
            * 13.0
        )

        pulse = (
            np.sin(
                2
                * np.pi
                * 62.0
                * local_t
            )
            * envelope
            * 0.055
        )

        audio[
            start:end
        ] += pulse.astype(
            np.float32
        )

    audio = np.clip(
        audio,
        -0.15,
        0.15,
    )

    output = Path(
        "generated/audio/"
        "narrative_movie_v7_sfx.wav"
    )

    output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    pcm = (
        audio
        * 32767
    ).astype(
        np.int16
    )

    with wave.open(
        str(output),
        "wb",
    ) as wav:

        wav.setnchannels(
            1
        )

        wav.setsampwidth(
            2
        )

        wav.setframerate(
            sample_rate
        )

        wav.writeframes(
            pcm.tobytes()
        )

    return AudioFileClip(
        str(output)
    )


############################################################
# V7 — FINAL SEQUENCE QA
############################################################

def final_sequence_qa_v7(
    moments,
):
    """
    Fail loudly on obvious weak sequences.
    """

    semantic_scores = [
        float(
            moment[
                "semantic"
            ]
        )
        for moment
        in moments
    ]

    quality_scores = [
        float(
            moment[
                "quality"
            ]
        )
        for moment
        in moments
    ]

    average_semantic = float(
        np.mean(
            semantic_scores
        )
    )

    minimum_semantic = float(
        np.min(
            semantic_scores
        )
    )

    average_quality = float(
        np.mean(
            quality_scores
        )
    )

    weak_semantic_count = sum(
        score < 0.15
        for score
        in semantic_scores
    )

    print()
    print(
        "========== V7 FINAL QA =========="
    )

    print(
        "AVG SEMANTIC:",
        round(
            average_semantic,
            4,
        ),
    )

    print(
        "MIN SEMANTIC:",
        round(
            minimum_semantic,
            4,
        ),
    )

    print(
        "AVG QUALITY:",
        round(
            average_quality,
            4,
        ),
    )

    print(
        "WEAK SEMANTIC SHOTS:",
        weak_semantic_count,
    )

    if weak_semantic_count > 3:

        raise RuntimeError(
            "V7 QA rejected sequence: "
            "too many weak semantic shots."
        )

    return {
        "average_semantic": (
            average_semantic
        ),
        "minimum_semantic": (
            minimum_semantic
        ),
        "average_quality": (
            average_quality
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


def build_voice(
    config,
):

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
        input=NARRATION,
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


def main():

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

    optimized_moments = (
        optimize_selected_moments_v6(
            source,
            entries,
            selected,
            model=model,
            preprocess=preprocess,
            tokenizer=tokenizer,
            device=device,
        )
    )

    final_sequence_qa_v7(
        optimized_moments
    )

    voice = build_voice(
        config
    )

    sfx = build_v7_sfx()

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

            entry = entries[
                scene_index
            ]

            moment = optimized_moments[
                index
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

            shot = shot.with_audio(
                None
            )

            focus_track = build_focus_track(
                source,
                start=float(start),
                end=float(end),
                samples=9,
            )

            shot = dynamic_crop_vertical(
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

            speed = (
                1.0
                + max(
                    0.0,
                    energy - 0.65,
                )
                * 0.07
            )

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
                caption_schedule_v7(
                    float(
                        voice.duration
                    )
                )
            )

        else:

            caption_schedule = []

        for caption_index, item in enumerate(
            caption_schedule
        ):

            caption_start = float(
                item[
                    "start"
                ]
            )

            caption_end = float(
                item[
                    "end"
                ]
            )

            caption_text = str(
                item[
                    "text"
                ]
            )

            emphasis = str(
                item[
                    "emphasis"
                ]
            )

            if (
                caption_end
                <= caption_start
            ):
                continue

            caption_y = caption_y_v7(
                source,
                optimized_moments,
                caption_start,
            )

            ################################################
            # Main phrase.
            ################################################

            caption = (
                TextClip(
                    text=caption_text,
                    font_size=52,
                    color="white",
                    stroke_color="black",
                    stroke_width=4,
                    method="caption",
                    size=(
                        760,
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
                        caption_y,
                    )
                )
            )

            captions.append(
                caption
            )

            ################################################
            # Keyword flash for emphasis.
            ################################################

            emphasis_duration = min(
                0.28,
                max(
                    0.16,
                    (
                        caption_end
                        - caption_start
                    )
                    * 0.34,
                ),
            )

            emphasis_clip = (
                TextClip(
                    text=emphasis,
                    font_size=59,
                    color="white",
                    stroke_color="black",
                    stroke_width=5,
                    method="caption",
                    size=(
                        700,
                        None,
                    ),
                    text_align="center",
                )
                .with_start(
                    caption_start
                )
                .with_duration(
                    emphasis_duration
                )
                .with_position(
                    (
                        "center",
                        caption_y
                        - 64,
                    )
                )
            )

            captions.append(
                emphasis_clip
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

            mixed_audio = CompositeAudioClip(
                [
                    voice,
                    sfx,
                ]
            )

            final = final.with_audio(
                mixed_audio
            )

        else:

            mixed_audio = sfx

            final = final.with_audio(
                mixed_audio
            )

        OUTPUT.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        print()
        print(
            "========== RENDERING NARRATIVE V7 =========="
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
            "========== V7 COMPLETE =========="
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

        try:
            sfx.close()
        except Exception:
            pass

        try:
            mixed_audio.close()
        except Exception:
            pass

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
