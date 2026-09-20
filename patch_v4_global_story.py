from pathlib import Path

path = Path(
    "render_narrative_movie_proof_v4.py"
)

text = path.read_text(
    encoding="utf-8"
)

start = text.find(
    "def choose_story("
)

end = text.find(
    "\ndef crop_vertical(",
    start,
)

if start < 0 or end < 0:
    raise RuntimeError(
        "choose_story block not found."
    )

replacement = r'''def choose_story(
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


'''

text = (
    text[:start]
    + replacement
    + text[end + 1:]
)

path.write_text(
    text,
    encoding="utf-8",
)

print(
    "SUCCESS: global narrative planner installed."
)
