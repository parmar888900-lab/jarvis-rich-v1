from pathlib import Path

path = Path(
    "render_narrative_movie_proof_v9.py"
)

text = path.read_text(
    encoding="utf-8"
)

############################################################
# IDENTITY
############################################################

text = text.replace(
    '"""Jarvis Rich V1 — global sequence editor V8."""',
    '"""Jarvis Rich V1 — editorial sequence editor V9."""',
    1,
)

text = text.replace(
    '"NARRATIVE_MOVIE_REFERENCE_PROOF_V8.mp4"',
    '"NARRATIVE_MOVIE_REFERENCE_PROOF_V9.mp4"',
)

text = text.replace(
    '"narrative_movie_v8.wav"',
    '"narrative_movie_v9.wav"',
)

text = text.replace(
    '"========== RENDERING NARRATIVE V8 =========="',
    '"========== RENDERING NARRATIVE V9 =========="',
)

text = text.replace(
    '"========== V8 COMPLETE =========="',
    '"========== V9 COMPLETE =========="',
)


############################################################
# INSERT V9 EDITORIAL SYSTEM
############################################################

anchor = "\ndef crop_vertical("

position = text.find(
    anchor
)

if position < 0:
    raise RuntimeError(
        "V9 insertion point not found."
    )

addition = r'''

############################################################
# V9 — EDITORIAL ROLE DEFINITIONS
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
# V9 — HARD WHOLE-SHOT HEALTH
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
# V9 — ROLE SCORES
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
# V9 — SPECIAL GLOBAL HOOK / END SEARCH
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
# V9 — HUMAN EDITOR GATE
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

            raise RuntimeError(
                "V9 editorial gate rejected every "
                f"candidate for beat {beat_index + 1}."
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
# V9 — FINAL ACCEPTANCE GATE
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
# V9 — STRONGER CLEAN CAPTIONS
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


'''

text = (
    text[:position]
    + addition
    + text[position:]
)


############################################################
# INSERT EDITORIAL POOL UPGRADE BEFORE BEAM SEARCH
############################################################

needle = '''    optimized_moments = (
        optimize_complete_sequence_v8(
            candidate_pools
        )
    )
'''

replacement = '''    candidate_pools = (
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
'''

if needle not in text:

    raise RuntimeError(
        "V8 global optimizer call not found."
    )

text = text.replace(
    needle,
    replacement,
    1,
)


############################################################
# USE STRICT V9 QA
############################################################

text = text.replace(
    '''    final_qa_v8(
        optimized_moments
    )''',
    '''    final_qa_v9(
        optimized_moments
    )''',
    1,
)


############################################################
# SPECIAL GLOBAL HOOK/ENDING MAY USE DIFFERENT SCENES.
# USE THE STORED scene_index_v9 DURING FINAL EXTRACTION.
############################################################

needle = '''            entry = entries[
                scene_index
            ]

            moment = optimized_moments[
                index
            ]
'''

replacement = '''            moment = optimized_moments[
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
'''

if needle not in text:

    raise RuntimeError(
        "V8 render scene block not found."
    )

text = text.replace(
    needle,
    replacement,
    1,
)


############################################################
# V9 CAPTIONS
############################################################

text = text.replace(
    '''                caption_schedule_v8(
                    float(
                        voice.duration
                    )
                )''',
    '''                caption_schedule_v9(
                    float(
                        voice.duration
                    )
                )''',
    1,
)

# V8 was slightly too timid.
text = text.replace(
    "font_size=54,",
    "font_size=60,",
    1,
)

text = text.replace(
    '''                    size=(
                        760,
                        None,
                    ),''',
    '''                    size=(
                        720,
                        None,
                    ),''',
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
    "SUCCESS: V9 editorial upgrade installed."
)
