from pathlib import Path

path = Path(
    "render_narrative_movie_proof_v6.py"
)

text = path.read_text(
    encoding="utf-8"
)

############################################################
# Identity / output
############################################################

text = text.replace(
    '"""Jarvis Rich V1 — narrative scene editor V5."""',
    '"""Jarvis Rich V1 — narrative scene editor V6."""',
    1,
)

text = text.replace(
    '"NARRATIVE_MOVIE_REFERENCE_PROOF_V5.mp4"',
    '"NARRATIVE_MOVIE_REFERENCE_PROOF_V6.mp4"',
)

text = text.replace(
    '"narrative_movie_v5.wav"',
    '"narrative_movie_v6.wav"',
)

text = text.replace(
    '"========== RENDERING NARRATIVE V5 =========="',
    '"========== RENDERING NARRATIVE V6 =========="',
)

text = text.replace(
    '"========== V5 COMPLETE =========="',
    '"========== V6 COMPLETE =========="',
)


############################################################
# Denser local search
############################################################

text = text.replace(
    "LOCAL_SAMPLE_COUNT = 7",
    "LOCAL_SAMPLE_COUNT = 11",
    1,
)

text = text.replace(
    "MAX_NEAR_DUPLICATE = 0.955",
    "MAX_NEAR_DUPLICATE = 0.945",
    1,
)


############################################################
# More human pacing:
# slower story setup -> increasingly fast climax.
# Exactly 37.0 seconds.
############################################################

start = text.find(
    "SHOT_DURATIONS = ["
)

end = text.find(
    "]",
    start,
)

if start < 0 or end < 0:
    raise RuntimeError(
        "SHOT_DURATIONS block not found."
    )

end += 1

new_durations = '''SHOT_DURATIONS = [
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
]'''

text = (
    text[:start]
    + new_durations
    + text[end:]
)


############################################################
# Insert V6 systems before crop_vertical()
############################################################

anchor = "\ndef crop_vertical("

insert_at = text.find(
    anchor
)

if insert_at < 0:
    raise RuntimeError(
        "crop_vertical insertion point not found."
    )

addition = r'''

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
                recent_embeddings[
                    -5:
                ]
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


'''

text = (
    text[:insert_at]
    + addition
    + text[insert_at:]
)


############################################################
# Use V6 optimizer
############################################################

text = text.replace(
    '''        optimize_selected_moments(
            source,
            entries,
            selected,''',
    '''        optimize_selected_moments_v6(
            source,
            entries,
            selected,''',
    1,
)


############################################################
# Replace static crop call in render loop
############################################################

old = '''            shot = crop_vertical(
                shot,
                moment[
                    "focus_x"
                ],
            )
'''

new = '''            focus_track = build_focus_track(
                source,
                start=float(start),
                end=float(end),
                samples=9,
            )

            shot = dynamic_crop_vertical(
                shot,
                focus_track,
            )
'''

if old not in text:
    raise RuntimeError(
        "Static crop render call not found."
    )

text = text.replace(
    old,
    new,
    1,
)


############################################################
# Use V6 caption scheduler
############################################################

text = text.replace(
    '''                build_synced_captions(
                    float(
                        voice.duration
                    )
                )''',
    '''                build_synced_captions_v6(
                    float(
                        voice.duration
                    )
                )''',
    1,
)


############################################################
# Smaller / safer caption layout
############################################################

text = text.replace(
    "font_size=68,",
    "font_size=56,",
    1,
)

text = text.replace(
    '''                    size=(
                        820,
                        None,
                    ),''',
    '''                    size=(
                        760,
                        None,
                    ),''',
    1,
)

text = text.replace(
    '''                        "center",
                        1160,''',
    '''                        "center",
                        990,''',
    1,
)


############################################################
# Save
############################################################

path.write_text(
    text,
    encoding="utf-8",
)

print(
    "SUCCESS: V6 installed."
)
