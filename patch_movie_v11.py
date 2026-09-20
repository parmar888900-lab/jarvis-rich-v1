from pathlib import Path

path = Path(
    "render_narrative_movie_proof_v11.py"
)

text = path.read_text(
    encoding="utf-8"
)


############################################################
# IDENTITY
############################################################

text = text.replace(
    "NARRATIVE_MOVIE_REFERENCE_PROOF_V10.mp4",
    "NARRATIVE_MOVIE_REFERENCE_PROOF_V11.mp4",
)

text = text.replace(
    "narrative_movie_v10.wav",
    "narrative_movie_v11.wav",
)

text = text.replace(
    "========== RENDERING NARRATIVE V10 ==========",
    "========== RENDERING NARRATIVE V11 ==========",
)

text = text.replace(
    "========== V10 COMPLETE ==========",
    "========== V11 COMPLETE ==========",
)


############################################################
# INSERT V11 EDITORIAL ENGINE
############################################################

anchor = "\ndef crop_vertical("

position = text.find(
    anchor
)

if position < 0:
    raise RuntimeError(
        "Could not locate V11 insertion point."
    )


addition = r'''

############################################################
# V11 — FINAL EDITORIAL ENGINE
############################################################

V11_BEAM_WIDTH = 120
V11_POOL_LIMIT = 8

V11_HARD_DUPLICATE = 0.972
V11_SOFT_DUPLICATE = 0.905

V11_MIN_RENDER_SCORE = 0.40

V11_MAX_BACKWARD_NORMAL = 18.0


############################################################
# V11 — IMPROVED SUBJECT TRACKING
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
# V11 — PREPARE EDITORIAL CANDIDATES
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
# V11 — GLOBAL EDITORIAL BEAM SEARCH
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
# V11 — NON-DESTRUCTIVE FINAL QA
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
# V11 — BETTER CAPTION SEGMENTATION
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


'''

text = (
    text[:position]
    + addition
    + text[position:]
)


############################################################
# V11 GLOBAL EDITOR:
# replace V10's final local polish stage.
############################################################

old = '''    optimized_moments = (
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
'''

new = '''    optimized_moments = (
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

    final_editorial_qa_v11(
        optimized_moments
    )
'''

if old not in text:

    raise RuntimeError(
        "Could not locate V10 polish integration."
    )

text = text.replace(
    old,
    new,
    1,
)


############################################################
# USE IMPROVED SUBJECT TRACKING
############################################################

old = '''build_focus_track_v8(
                    source,
                    start=float(start),
                    end=float(end),
                )'''

new = '''build_focus_track_v11(
                    source,
                    start=float(start),
                    end=float(end),
                )'''

if old not in text:

    raise RuntimeError(
        "Could not locate V8 focus track render call."
    )

text = text.replace(
    old,
    new,
    1,
)


############################################################
# REMOVE AUTOMATIC SPEED-UP
#
# Artificial speed scaling was contributing to an algorithmic
# feeling and can create unnatural motion.
############################################################

old = '''            speed = (
                1.0
                + max(
                    0.0,
                    energy - 0.65,
                )
                * 0.07
            )
'''

new = '''            # V11:
            # preserve original cinematic motion.
            speed = 1.0
'''

if old not in text:

    raise RuntimeError(
        "Could not locate V10 speed variation block."
    )

text = text.replace(
    old,
    new,
    1,
)


############################################################
# USE V11 CAPTIONS
############################################################

old = '''caption_schedule_v10(
                    float(
                        voice.duration
                    )
                )'''

new = '''caption_schedule_v11(
                    float(
                        voice.duration
                    )
                )'''

if old not in text:

    raise RuntimeError(
        "Could not locate V10 caption scheduler call."
    )

text = text.replace(
    old,
    new,
    1,
)


############################################################
# STRONGER SHORTS CAPTION PRESENTATION
############################################################

text = text.replace(
    "font_size=66,",
    "font_size=74,",
    1,
)

text = text.replace(
    "stroke_width=4,",
    "stroke_width=5,",
    1,
)

text = text.replace(
    '''                    size=(
                        780,
                        None,
                    ),''',
    '''                    size=(
                        840,
                        None,
                    ),''',
    1,
)

text = text.replace(
    '''                        "center",
                        955,''',
    '''                        "center",
                        980,''',
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
    "SUCCESS: V11 editorial consolidation installed."
)
