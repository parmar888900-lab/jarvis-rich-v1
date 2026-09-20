from pathlib import Path

path = Path(
    "render_narrative_movie_proof_v9.py"
)

text = path.read_text(
    encoding="utf-8"
)

old = '''        if not accepted:

            raise RuntimeError(
                "V9 editorial gate rejected every "
                f"candidate for beat {beat_index + 1}."
            )
'''

new = r'''        if not accepted:

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
'''

if old not in text:
    raise RuntimeError(
        "V9 rejection block not found."
    )

text = text.replace(
    old,
    new,
    1,
)

path.write_text(
    text,
    encoding="utf-8",
)

print(
    "SUCCESS: V9 editorial recovery installed."
)
