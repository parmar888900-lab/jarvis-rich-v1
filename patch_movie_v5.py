from pathlib import Path

path = Path("render_narrative_movie_proof_v5.py")

text = path.read_text(
    encoding="utf-8"
)

############################################################
# Rename outputs / identity
############################################################

text = text.replace(
    '"""Jarvis Rich V1 — narrative scene editor V4."""',
    '"""Jarvis Rich V1 — narrative scene editor V5."""',
    1,
)

text = text.replace(
    '"NARRATIVE_MOVIE_REFERENCE_PROOF_V4.mp4"',
    '"NARRATIVE_MOVIE_REFERENCE_PROOF_V5.mp4"',
)

text = text.replace(
    '"narrative_movie_v4.wav"',
    '"narrative_movie_v5.wav"',
)

text = text.replace(
    '"========== RENDERING NARRATIVE V4 =========="',
    '"========== RENDERING NARRATIVE V5 =========="',
)

text = text.replace(
    '"========== V4 COMPLETE =========="',
    '"========== V5 COMPLETE =========="',
)

############################################################
# Add V5 constants after SEARCH_END
############################################################

anchor = '''SEARCH_START = 20.0
SEARCH_END = 580.0
'''

replacement = '''SEARCH_START = 20.0
SEARCH_END = 580.0

# V5 ranking / QA.
LOCAL_SAMPLE_COUNT = 7

MIN_LOCAL_SEMANTIC = 0.145
MIN_LOCAL_QUALITY = 0.22

MAX_NEAR_DUPLICATE = 0.955

ENERGY_CURVE = (
    0.20, 0.22, 0.24, 0.28, 0.30, 0.34,
    0.37, 0.40, 0.43, 0.47, 0.50, 0.54,
    0.58, 0.62, 0.67, 0.72, 0.77, 0.82,
    0.87, 0.91, 0.96, 1.00,
)
'''

if anchor not in text:
    raise RuntimeError(
        "V5 constant insertion point not found."
    )

text = text.replace(
    anchor,
    replacement,
    1,
)

############################################################
# Insert V5 local shot-analysis functions before crop_vertical
############################################################

anchor = "\ndef crop_vertical("

index = text.find(anchor)

if index < 0:
    raise RuntimeError(
        "crop_vertical insertion point not found."
    )

addition = r'''

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


'''

text = (
    text[:index]
    + addition
    + text[index:]
)

############################################################
# Replace clip extraction block to use optimized local moments
############################################################

old = '''    selected = choose_story(
        entries,
        scene_features,
        prompts,
    )

    voice = build_voice(
        config
    )

    clips = []
'''

new = '''    selected = choose_story(
        entries,
        scene_features,
        prompts,
    )

    optimized_moments = (
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

    voice = build_voice(
        config
    )

    clips = []
'''

if old not in text:
    raise RuntimeError(
        "Could not insert local optimizer."
    )

text = text.replace(
    old,
    new,
    1,
)

############################################################
# Replace V4 shot assembly loop
############################################################

start = text.find(
    '''        for index, (
            scene_index,
            duration,
        ) in enumerate(
'''
)

end = text.find(
    '''        base = concatenate_videoclips(
''',
    start,
)

if start < 0 or end < 0:
    raise RuntimeError(
        "Shot assembly block not found."
    )

replacement = r'''        for index, (
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

            shot = crop_vertical(
                shot,
                moment[
                    "focus_x"
                ],
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

'''

text = (
    text[:start]
    + replacement
    + text[end:]
)

############################################################
# Replace fixed captions with narration-synced captions
############################################################

start = text.find(
    '''        position = 0.0

        for index, duration in enumerate(
'''
)

end = text.find(
    '''        final = CompositeVideoClip(
''',
    start,
)

if start < 0 or end < 0:
    raise RuntimeError(
        "Caption block not found."
    )

replacement = r'''        ####################################################
        # Narration-synchronized phrase captions.
        ####################################################

        if voice is not None:

            caption_schedule = (
                build_synced_captions(
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
                    font_size=68,
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
                    caption_start
                )
                .with_duration(
                    caption_end
                    - caption_start
                )
                .with_position(
                    (
                        "center",
                        1160,
                    )
                )
            )

            captions.append(
                caption
            )

'''

text = (
    text[:start]
    + replacement
    + text[end:]
)

############################################################
# Save V5
############################################################

path.write_text(
    text,
    encoding="utf-8",
)

print(
    "SUCCESS: V5 upgrade installed."
)
