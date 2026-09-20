from pathlib import Path

path = Path("render_narrative_movie_proof_v8.py")

text = path.read_text(
    encoding="utf-8"
)

############################################################
# IDENTITY
############################################################

text = text.replace(
    '"""Jarvis Rich V1 — narrative scene editor V5."""',
    '"""Jarvis Rich V1 — global sequence editor V8."""',
    1,
)

text = text.replace(
    '"NARRATIVE_MOVIE_REFERENCE_PROOF_V5.mp4"',
    '"NARRATIVE_MOVIE_REFERENCE_PROOF_V8.mp4"',
)

text = text.replace(
    '"narrative_movie_v5.wav"',
    '"narrative_movie_v8.wav"',
)

text = text.replace(
    '"========== RENDERING NARRATIVE V5 =========="',
    '"========== RENDERING NARRATIVE V8 =========="',
)

text = text.replace(
    '"========== V5 COMPLETE =========="',
    '"========== V8 COMPLETE =========="',
)

text = text.replace(
    "LOCAL_SAMPLE_COUNT = 7",
    "LOCAL_SAMPLE_COUNT = 13",
    1,
)

text = text.replace(
    "MAX_NEAR_DUPLICATE = 0.955",
    "MAX_NEAR_DUPLICATE = 0.935",
    1,
)

############################################################
# INSERT V8 SYSTEMS
############################################################

anchor = "\ndef crop_vertical("

pos = text.find(anchor)

if pos < 0:
    raise RuntimeError("Insertion point not found.")

addition = r'''

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


'''

text = (
    text[:pos]
    + addition
    + text[pos:]
)

############################################################
# REPLACE V5 LOCAL OPTIMIZATION
############################################################

old = '''    optimized_moments = (
        optimize_selected_moments(
            source,
            entries,
            selected,
            model=model,
            preprocess=preprocess,
            tokenizer=tokenizer,
            device=device,
        )
    )
'''

new = '''    candidate_pools = (
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
'''

if old not in text:
    raise RuntimeError(
        "V5 optimizer call not found."
    )

text = text.replace(
    old,
    new,
    1,
)

############################################################
# REPLACE STATIC CROP
############################################################

old = '''            shot = crop_vertical(
                shot,
                moment[
                    "focus_x"
                ],
            )
'''

new = '''            focus_track = (
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
'''

if old not in text:
    raise RuntimeError(
        "Static crop call not found."
    )

text = text.replace(
    old,
    new,
    1,
)

############################################################
# REPLACE CAPTION SCHEDULER
############################################################

text = text.replace(
    '''                build_synced_captions(
                    float(
                        voice.duration
                    )
                )''',
    '''                caption_schedule_v8(
                    float(
                        voice.duration
                    )
                )''',
    1,
)

############################################################
# IMPROVE CAPTION SIZE / POSITION
############################################################

text = text.replace(
    "font_size=68,",
    "font_size=54,",
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
# SAVE
############################################################

path.write_text(
    text,
    encoding="utf-8",
)

print(
    "SUCCESS: V8 installed."
)
