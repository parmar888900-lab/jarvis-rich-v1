from pathlib import Path

path = Path(
    "render_narrative_movie_proof_v12.py"
)

text = path.read_text(
    encoding="utf-8"
)


############################################################
# IDENTITY
############################################################

text = text.replace(
    "NARRATIVE_MOVIE_REFERENCE_PROOF_V11.mp4",
    "NARRATIVE_MOVIE_REFERENCE_PROOF_V12.mp4",
)

text = text.replace(
    "narrative_movie_v11.wav",
    "narrative_movie_v12.wav",
)

text = text.replace(
    "========== RENDERING NARRATIVE V11 ==========",
    "========== RENDERING NARRATIVE V12 ==========",
)

text = text.replace(
    "========== V11 COMPLETE ==========",
    "========== V12 COMPLETE ==========",
)


############################################################
# INSERT V12 PRESENTATION ENGINE
############################################################

anchor = "\ndef crop_vertical("

position = text.find(
    anchor
)

if position < 0:
    raise RuntimeError(
        "Could not find V12 insertion point."
    )


addition = r'''

############################################################
# V12 — PRESENTATION POLISH
############################################################

V12_FONT_PATH = Path(
    r"C:\Windows\Fonts\arialbd.ttf"
)

V12_FONT = (
    str(
        V12_FONT_PATH
    )
    if V12_FONT_PATH.is_file()
    else None
)


############################################################
# V12 — SURGICAL HOOK + ENDING REFINEMENT
############################################################

def refine_hook_and_ending_v12(
    pools,
    sequence,
):
    """
    Preserve the complete V11 sequence except beats 1 and 22.

    Those two beats have special editorial jobs:
        1 = stop the scroll
        22 = provide payoff
    """

    print()
    print(
        "========== V12 HOOK / ENDING POLISH =========="
    )

    output = list(
        sequence
    )

    ########################################################
    # HOOK
    ########################################################

    second = output[
        1
    ]

    best_hook = output[
        0
    ]

    best_hook_score = -999.0

    for candidate in pools[
        0
    ]:

        render = float(
            candidate.get(
                "v11_render_score",
                0.0,
            )
        )

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

        hook_margin = float(
            candidate.get(
                "hook_margin",
                0.0,
            )
        )

        similarity_to_next = float(
            (
                candidate[
                    "embedding"
                ]
                @ second[
                    "embedding"
                ]
            ).item()
        )

        repetition_penalty = max(
            0.0,
            similarity_to_next
            - 0.90,
        ) * 0.65

        score = (
            render * 0.31
            + semantic * 0.19
            + composition * 0.17
            + motion * 0.21
            + hook_margin * 0.12
            - repetition_penalty
        )

        if score > best_hook_score:

            best_hook_score = score
            best_hook = candidate

    output[
        0
    ] = best_hook

    print(
        "HOOK:",
        round(
            float(
                best_hook[
                    "timestamp"
                ]
            ),
            2,
        ),
        "sec",
        "| score:",
        round(
            best_hook_score,
            4,
        ),
        "| render:",
        round(
            float(
                best_hook.get(
                    "v11_render_score",
                    0.0,
                )
            ),
            3,
        ),
    )

    ########################################################
    # ENDING
    ########################################################

    previous = output[
        -2
    ]

    best_end = output[
        -1
    ]

    best_end_score = -999.0

    for candidate in pools[
        -1
    ]:

        render = float(
            candidate.get(
                "v11_render_score",
                0.0,
            )
        )

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

        ending_margin = float(
            candidate.get(
                "ending_margin",
                0.0,
            )
        )

        similarity_to_previous = float(
            (
                candidate[
                    "embedding"
                ]
                @ previous[
                    "embedding"
                ]
            ).item()
        )

        repetition_penalty = max(
            0.0,
            similarity_to_previous
            - 0.91,
        ) * 0.65

        score = (
            render * 0.30
            + semantic * 0.17
            + composition * 0.14
            + motion * 0.25
            + ending_margin * 0.14
            - repetition_penalty
        )

        if score > best_end_score:

            best_end_score = score
            best_end = candidate

    output[
        -1
    ] = best_end

    print(
        "ENDING:",
        round(
            float(
                best_end[
                    "timestamp"
                ]
            ),
            2,
        ),
        "sec",
        "| score:",
        round(
            best_end_score,
            4,
        ),
        "| render:",
        round(
            float(
                best_end.get(
                    "v11_render_score",
                    0.0,
                )
            ),
            3,
        ),
    )

    return output


############################################################
# V12 — TITLE / SOURCE ARTIFACT PROTECTION
############################################################

def prepare_source_shot_v12(
    shot,
    *,
    beat_index: int,
):
    """
    Tears of Steel contains source-film/title material near
    frame edges in some shots.

    For the critical opening only, remove a narrow lower strip
    before vertical reframing.

    This is intentionally conservative.
    """

    if beat_index != 0:

        return shot

    trim_bottom = (
        shot.h
        * 0.055
    )

    usable_height = (
        shot.h
        - trim_bottom
    )

    if usable_height <= 0:

        return shot

    return shot.cropped(
        x1=0,
        y1=0,
        x2=shot.w,
        y2=usable_height,
    )


############################################################
# V12 — CAPTION SEGMENTATION
############################################################

def caption_chunks_v12():
    """
    Human-readable short subtitle phrases.

    Primary rule:
        2-3 spoken words per card.

    Strong punctuation starts a new phrase.
    """

    import re

    tokens = re.findall(
        r"[A-Za-z0-9']+|[,.!?;:]",
        NARRATION,
    )

    chunks = []

    current = []

    pattern = (
        2,
        3,
        2,
        3,
        2,
        3,
    )

    pattern_index = 0

    strong_breaks = {
        ".",
        "!",
        "?",
        ";",
        ":",
    }

    for token in tokens:

        if token in strong_breaks:

            if current:

                chunks.append(
                    " ".join(
                        current
                    ).upper()
                )

                current = []

                pattern_index += 1

            continue

        if token == ",":

            if len(
                current
            ) >= 2:

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

        target = pattern[
            pattern_index
            % len(
                pattern
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

    ########################################################
    # Avoid orphan one-word cards where possible.
    ########################################################

    repaired = []

    for chunk in chunks:

        words = chunk.split()

        if (
            len(words) == 1
            and repaired
            and len(
                repaired[
                    -1
                ].split()
            ) <= 2
        ):

            repaired[
                -1
            ] = (
                repaired[
                    -1
                ]
                + " "
                + chunk
            )

        else:

            repaired.append(
                chunk
            )

    return repaired


############################################################
# V12 — AUDIO-ENERGY SPEECH ALIGNMENT
############################################################

def speech_energy_v12():
    """
    Read the generated Piper WAV and produce a low-cost
    speech-energy curve.

    This allows subtitle boundaries to move toward natural
    speech pauses without adding Whisper or another model.
    """

    import wave

    if not VOICE_OUTPUT.is_file():

        return None

    try:

        with wave.open(
            str(
                VOICE_OUTPUT
            ),
            "rb",
        ) as wav:

            sample_rate = wav.getframerate()

            channels = wav.getnchannels()

            width = wav.getsampwidth()

            frames = wav.getnframes()

            raw = wav.readframes(
                frames
            )

    except Exception:

        return None

    if width != 2:

        return None

    samples = np.frombuffer(
        raw,
        dtype=np.int16,
    ).astype(
        np.float32
    )

    if channels > 1:

        samples = samples.reshape(
            -1,
            channels,
        ).mean(
            axis=1
        )

    samples /= 32768.0

    if len(
        samples
    ) == 0:

        return None

    window_seconds = 0.025

    window = max(
        1,
        int(
            sample_rate
            * window_seconds
        ),
    )

    energies = []

    times = []

    for start in range(
        0,
        len(samples),
        window,
    ):

        block = samples[
            start:
            start + window
        ]

        if len(
            block
        ) == 0:

            continue

        energy = float(
            np.mean(
                np.abs(
                    block
                )
            )
        )

        energies.append(
            energy
        )

        times.append(
            start
            / sample_rate
        )

    return (
        np.array(
            times,
            dtype=np.float32,
        ),
        np.array(
            energies,
            dtype=np.float32,
        ),
    )


def snap_to_speech_pause_v12(
    target_time,
    energy_data,
):
    """
    Move an estimated caption boundary toward the quietest
    local speech point.

    Maximum adjustment is small to protect synchronization.
    """

    if energy_data is None:

        return float(
            target_time
        )

    times, energy = energy_data

    if len(
        times
    ) == 0:

        return float(
            target_time
        )

    search_radius = 0.16

    mask = (
        times
        >= target_time
        - search_radius
    ) & (
        times
        <= target_time
        + search_radius
    )

    indexes = np.where(
        mask
    )[0]

    if len(
        indexes
    ) == 0:

        return float(
            target_time
        )

    best_index = indexes[
        int(
            np.argmin(
                energy[
                    indexes
                ]
            )
        )
    ]

    snapped = float(
        times[
            best_index
        ]
    )

    ########################################################
    # Do not over-correct.
    ########################################################

    if abs(
        snapped
        - target_time
    ) > search_radius:

        return float(
            target_time
        )

    return snapped


def caption_schedule_v12(
    voice_duration,
):
    """
    Phrase timing:
        text-length estimate
        +
        real Piper WAV pause detection
    """

    chunks = (
        caption_chunks_v12()
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
            0.75
            + min(
                len(word),
                11,
            )
            / 6.7
            for word
            in words
        )

        weights.append(
            float(
                weight
            )
        )

    total = max(
        sum(
            weights
        ),
        1.0,
    )

    boundaries = [
        0.0
    ]

    running = 0.0

    for weight in weights:

        running += weight

        boundaries.append(
            usable
            * running
            / total
        )

    energy_data = (
        speech_energy_v12()
    )

    adjusted = [
        0.0
    ]

    for boundary in boundaries[
        1:-1
    ]:

        adjusted.append(
            snap_to_speech_pause_v12(
                boundary,
                energy_data,
            )
        )

    adjusted.append(
        usable
    )

    ########################################################
    # Enforce monotonic boundaries and minimum display time.
    ########################################################

    minimum_duration = 0.22

    cleaned = [
        0.0
    ]

    for boundary in adjusted[
        1:
    ]:

        boundary = max(
            boundary,
            cleaned[
                -1
            ]
            + minimum_duration,
        )

        boundary = min(
            boundary,
            usable,
        )

        cleaned.append(
            boundary
        )

    cleaned[
        -1
    ] = usable

    schedule = []

    for index, chunk in enumerate(
        chunks
    ):

        if (
            index + 1
            >= len(
                cleaned
            )
        ):

            break

        start = float(
            cleaned[
                index
            ]
        )

        end = float(
            cleaned[
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


############################################################
# V12 — PRESENTATION QA
############################################################

def final_presentation_qa_v12(
    moments,
):
    """
    Presentation-oriented diagnostics.

    Does not re-reject the complete edit for minor score
    imperfections.
    """

    print()
    print(
        "========== V12 PRESENTATION QA =========="
    )

    hook = moments[
        0
    ]

    ending = moments[
        -1
    ]

    hook_score = (
        float(
            hook.get(
                "v11_render_score",
                0.0,
            )
        ) * 0.42

        + float(
            hook.get(
                "motion",
                0.0,
            )
        ) * 0.28

        + float(
            hook.get(
                "semantic",
                0.0,
            )
        ) * 0.18

        + float(
            hook.get(
                "composition",
                0.0,
            )
        ) * 0.12
    )

    end_score = (
        float(
            ending.get(
                "v11_render_score",
                0.0,
            )
        ) * 0.38

        + float(
            ending.get(
                "motion",
                0.0,
            )
        ) * 0.34

        + float(
            ending.get(
                "semantic",
                0.0,
            )
        ) * 0.16

        + float(
            ending.get(
                "composition",
                0.0,
            )
        ) * 0.12
    )

    timestamps = [
        float(
            item[
                "timestamp"
            ]
        )
        for item
        in moments
    ]

    backwards = []

    for index in range(
        1,
        len(
            timestamps
        ) - 1,
    ):

        jump = (
            timestamps[
                index
            ]
            - timestamps[
                index - 1
            ]
        )

        if jump < -8.0:

            backwards.append(
                (
                    index + 1,
                    round(
                        jump,
                        2,
                    ),
                )
            )

    print(
        "HOOK PRESENTATION SCORE:",
        round(
            hook_score,
            4,
        ),
    )

    print(
        "ENDING PRESENTATION SCORE:",
        round(
            end_score,
            4,
        ),
    )

    print(
        "BACKWARD STORY JUMPS:",
        backwards,
    )

    print(
        "CAPTION SYSTEM:",
        "PUNCTUATION + SPEECH-PAUSE ALIGNED",
    )

    print(
        "SOURCE ARTIFACT PROTECTION:",
        "ENABLED FOR HOOK",
    )

    return {
        "hook": hook_score,
        "ending": end_score,
        "backward_jumps": (
            backwards
        ),
    }


'''

text = (
    text[:position]
    + addition
    + text[position:]
)


############################################################
# REFINE HOOK + ENDING AFTER V11 GLOBAL EDITOR
############################################################

old = '''    optimized_moments = (
        optimize_sequence_v11(
            v11_candidate_pools
        )
    )

    final_editorial_qa_v11(
        optimized_moments
    )
'''

new = '''    optimized_moments = (
        optimize_sequence_v11(
            v11_candidate_pools
        )
    )

    optimized_moments = (
        refine_hook_and_ending_v12(
            v11_candidate_pools,
            optimized_moments,
        )
    )

    final_editorial_qa_v11(
        optimized_moments
    )

    final_presentation_qa_v12(
        optimized_moments
    )
'''

if old not in text:

    raise RuntimeError(
        "Could not wire V12 hook/end polish."
    )

text = text.replace(
    old,
    new,
    1,
)


############################################################
# APPLY SOURCE-ARTIFACT PROTECTION TO OPENING
############################################################

old = '''            shot = source.subclipped(
                start,
                end,
            )

            shot = shot.with_audio(
                None
            )
'''

new = '''            shot = source.subclipped(
                start,
                end,
            )

            shot = prepare_source_shot_v12(
                shot,
                beat_index=index,
            )

            shot = shot.with_audio(
                None
            )
'''

if old not in text:

    raise RuntimeError(
        "Could not locate V11 shot creation."
    )

text = text.replace(
    old,
    new,
    1,
)


############################################################
# V12 CAPTION SCHEDULER
############################################################

old = '''caption_schedule_v11(
                    float(
                        voice.duration
                    )
                )'''

new = '''caption_schedule_v12(
                    float(
                        voice.duration
                    )
                )'''

if old not in text:

    raise RuntimeError(
        "Could not locate V11 caption scheduler."
    )

text = text.replace(
    old,
    new,
    1,
)


############################################################
# TYPOGRAPHY
############################################################

text = text.replace(
    '''text=caption_text,
                    font_size=74,''',
    '''text=caption_text,
                    font=V12_FONT,
                    font_size=82,''',
    1,
)

text = text.replace(
    "stroke_width=5,",
    "stroke_width=7,",
    1,
)

text = text.replace(
    '''                    size=(
                        840,
                        None,
                    ),''',
    '''                    size=(
                        870,
                        None,
                    ),''',
    1,
)

text = text.replace(
    '''                        "center",
                        980,''',
    '''                        "center",
                        1010,''',
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
    "SUCCESS: V12 presentation polish installed."
)
