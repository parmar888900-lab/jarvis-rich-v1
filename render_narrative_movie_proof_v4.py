"""Jarvis Rich V1 — narrative scene editor V4."""

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
    "NARRATIVE_MOVIE_REFERENCE_PROOF_V4.mp4"
)

VOICE_OUTPUT = Path(
    "generated/audio/"
    "narrative_movie_v4.wav"
)

# Avoid the film's credits entirely for this benchmark.
SEARCH_START = 20.0
SEARCH_END = 580.0

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

            scene_duration = (
                entry[
                    "end"
                ]
                - entry[
                    "start"
                ]
            )

            center = entry[
                "center"
            ]

            start = max(
                entry[
                    "start"
                ],
                center
                - duration / 2,
            )

            if (
                start + duration
                > entry[
                    "end"
                ]
            ):

                start = max(
                    entry[
                        "start"
                    ],
                    entry[
                        "end"
                    ]
                    - duration,
                )

            end = min(
                source.duration,
                start + duration,
            )

            shot = source.subclipped(
                start,
                end,
            )

            shot = shot.with_audio(
                None
            )

            shot = crop_vertical(
                shot,
                entry[
                    "focus_x"
                ],
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
        ).with_duration(
            TARGET_DURATION
        )

        position = 0.0

        for index, duration in enumerate(
            SHOT_DURATIONS
        ):

            if index in CAPTIONS:

                caption = (
                    TextClip(
                        text=CAPTIONS[
                            index
                        ],
                        font_size=72,
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
                        position
                    )
                    .with_duration(
                        min(
                            duration,
                            1.4,
                        )
                    )
                    .with_position(
                        (
                            "center",
                            1180,
                        )
                    )
                )

                captions.append(
                    caption
                )

            position += duration

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
            "========== RENDERING NARRATIVE V4 =========="
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
            "========== V4 COMPLETE =========="
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
