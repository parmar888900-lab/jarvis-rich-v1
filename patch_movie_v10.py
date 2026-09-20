from pathlib import Path

path = Path(
    "render_narrative_movie_proof_v10.py"
)

text = path.read_text(
    encoding="utf-8"
)

############################################################
# IDENTITY
############################################################

text = text.replace(
    '"""Jarvis Rich V1 — editorial sequence editor V9."""',
    '"""Jarvis Rich V1 — surgical polish editor V10."""',
    1,
)

text = text.replace(
    '"NARRATIVE_MOVIE_REFERENCE_PROOF_V9.mp4"',
    '"NARRATIVE_MOVIE_REFERENCE_PROOF_V10.mp4"',
    1,
)

text = text.replace(
    '"narrative_movie_v9.wav"',
    '"narrative_movie_v10.wav"',
    1,
)

text = text.replace(
    '"========== RENDERING NARRATIVE V9 =========="',
    '"========== RENDERING NARRATIVE V10 =========="',
    1,
)

text = text.replace(
    '"========== V9 COMPLETE =========="',
    '"========== V10 COMPLETE =========="',
    1,
)


############################################################
# V10 FUNCTIONS
############################################################

anchor = "\ndef crop_vertical("

insert_at = text.find(
    anchor
)

if insert_at < 0:
    raise RuntimeError(
        "Could not locate crop_vertical insertion point."
    )

addition = r'''

############################################################
# V10 — SURGICAL RENDER QA
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

    valid = (
        blown < 0.17
        and crushed < 0.62
        and contrast >= 17.0
        and sharpness >= 18.0
        and entropy >= 2.8
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

    valid = (
        bad_ratio <= 0.29
        and blown < 0.12
        and minimum >= 0.25
        and render_score >= 0.48
    )

    if (
        beat_index in FACE_BEATS
        and face_margin < -0.095
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
# V10 — SURGICAL SHOT REPLACEMENT
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
        "========== V10 RENDERED-FRAME QA =========="
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
# V10 — FINAL POLISH QA
############################################################

def final_polish_qa_v10(
    source,
    entries,
    selected,
    moments,
):
    print()
    print(
        "========== V10 FINAL POLISH QA =========="
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

    if len(
        failures
    ) > 2:

        raise RuntimeError(
            "V10 final polish QA rejected the edit. "
            f"Failed beats: {failures}"
        )

    if average < 0.52:

        raise RuntimeError(
            "V10 final polish QA rejected the edit: "
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
# V10 — CAPTIONS THAT SPAN THE FULL VOICE
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


'''

text = (
    text[:insert_at]
    + addition
    + text[insert_at:]
)


############################################################
# WIRE V10 AFTER THE GLOBAL OPTIMIZER
############################################################

old = '''    optimized_moments = (
        optimize_complete_sequence_v8(
            candidate_pools
        )
    )

    final_qa_v9(
        optimized_moments
    )

    voice = build_voice(
        config
    )
'''

new = '''    optimized_moments = (
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

    final_polish_qa_v10(
        source,
        entries,
        selected,
        optimized_moments,
    )

    voice = build_voice(
        config
    )
'''

if old not in text:
    raise RuntimeError(
        "Could not wire V10 after V9 optimizer."
    )

text = text.replace(
    old,
    new,
    1,
)


############################################################
# CAPTION SCHEDULER
############################################################

old = '''caption_schedule_v9(
                    float(
                        voice.duration
                    )
                )'''

new = '''caption_schedule_v10(
                    float(
                        voice.duration
                    )
                )'''

if old not in text:
    raise RuntimeError(
        "Could not replace V9 caption scheduler."
    )

text = text.replace(
    old,
    new,
    1,
)


############################################################
# STRONGER BUT CLEAN CAPTION PRESENTATION
############################################################

text = text.replace(
    "font_size=60,",
    "font_size=66,",
    1,
)

text = text.replace(
    '''                    size=(
                        720,
                        None,
                    ),''',
    '''                    size=(
                        780,
                        None,
                    ),''',
    1,
)

text = text.replace(
    '''                        "center",
                        990,''',
    '''                        "center",
                        955,''',
    1,
)


############################################################
# WRITE
############################################################

path.write_text(
    text,
    encoding="utf-8",
)

print(
    "SUCCESS: V10 surgical polish installed."
)
