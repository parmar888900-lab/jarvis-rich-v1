"""Jarvis Rich V1 — global sequence editor V8."""

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
    "NARRATIVE_MOVIE_REFERENCE_PROOF_V8.mp4"
)

VOICE_OUTPUT = Path(
    "generated/audio/"
    "narrative_movie_v8.wav"
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
# V8 — WHOLE-SHOT QUALITY
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
# V8 — CANDIDATE POOLS
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
# V8 — GLOBAL EXACT-SHOT BEAM SEARCH
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
# V8 — DYNAMIC SUBJECT TRACK
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
# V8 — CLEANER CAPTIONS
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
# V8 — FINAL QA
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

    optimized_moments = (
        optimize_complete_sequence_v8(
            candidate_pools
        )
    )

    final_qa_v8(
        optimized_moments
    )

    voice = build_voice(
        config
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

            focus_track = (
                build_focus_track_v8(
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
                caption_schedule_v8(
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
                    font_size=54,
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
                        990,
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
            "========== RENDERING NARRATIVE V8 =========="
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
            "========== V8 COMPLETE =========="
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
