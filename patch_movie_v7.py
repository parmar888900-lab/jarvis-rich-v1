from pathlib import Path

path = Path(
    "render_narrative_movie_proof_v7.py"
)

text = path.read_text(
    encoding="utf-8"
)

############################################################
# IDENTITY
############################################################

text = text.replace(
    '"""Jarvis Rich V1 — narrative scene editor V6."""',
    '"""Jarvis Rich V1 — narrative scene editor V7."""',
    1,
)

text = text.replace(
    '"NARRATIVE_MOVIE_REFERENCE_PROOF_V6.mp4"',
    '"NARRATIVE_MOVIE_REFERENCE_PROOF_V7.mp4"',
)

text = text.replace(
    '"narrative_movie_v6.wav"',
    '"narrative_movie_v7.wav"',
)

text = text.replace(
    '"========== RENDERING NARRATIVE V6 =========="',
    '"========== RENDERING NARRATIVE V7 =========="',
)

text = text.replace(
    '"========== V6 COMPLETE =========="',
    '"========== V7 COMPLETE =========="',
)


############################################################
# STRONGER GLOBAL DUPLICATE REJECTION
############################################################

text = text.replace(
    "MAX_NEAR_DUPLICATE = 0.945",
    "MAX_NEAR_DUPLICATE = 0.925",
    1,
)

# V6 only compared recent shots.
# V7 compares against ALL previously selected shots.
text = text.replace(
    '''recent_embeddings[
                    -5:
                ]''',
    '''recent_embeddings''',
)


############################################################
# IMPORTS FOR AUDIO MIX
############################################################

old_import = '''from moviepy import (
    AudioFileClip,
    CompositeVideoClip,
'''

new_import = '''from moviepy import (
    AudioFileClip,
    CompositeAudioClip,
    CompositeVideoClip,
'''

if old_import in text:
    text = text.replace(
        old_import,
        new_import,
        1,
    )


############################################################
# ADD V7 SYSTEMS
############################################################

anchor = "\ndef crop_vertical("

position = text.find(
    anchor
)

if position < 0:
    raise RuntimeError(
        "V7 insertion point not found."
    )

addition = r'''

############################################################
# V7 — STRONGER HOOK RANKING
############################################################

def rerank_hook_v7(
    candidates,
):
    """
    The first shot has a different job from normal beats:
    stop the scroll.

    Favor:
      semantic relevance
      composition
      motion
      visual quality
    """

    if not candidates:
        return candidates

    for item in candidates:

        item[
            "hook_score"
        ] = (
            item[
                "semantic"
            ] * 0.34
            + item[
                "composition"
            ] * 0.25
            + item[
                "quality"
            ] * 0.23
            + item[
                "motion"
            ] * 0.18
        )

    return sorted(
        candidates,
        key=lambda item: item[
            "hook_score"
        ],
        reverse=True,
    )


############################################################
# V7 — CAPTION PHRASES
############################################################

def caption_phrases_v7():
    """
    Short 2-3 word phrases.

    This is intentionally denser than V6's caption blocks
    and closer to modern commentary subtitles.
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

    phrases = []

    pattern = (
        2,
        3,
        2,
        3,
        3,
        2,
    )

    cursor = 0
    pattern_index = 0

    while cursor < len(
        words
    ):

        size = pattern[
            pattern_index
            % len(pattern)
        ]

        phrase_words = words[
            cursor:
            cursor + size
        ]

        if not phrase_words:
            break

        # Longest word becomes emphasis word.
        emphasis = max(
            phrase_words,
            key=len,
        )

        phrases.append(
            {
                "text": " ".join(
                    phrase_words
                ).upper(),
                "emphasis": (
                    emphasis.upper()
                ),
                "word_count": len(
                    phrase_words
                ),
                "weight": sum(
                    max(
                        1.0,
                        len(word) / 4.4,
                    )
                    for word
                    in phrase_words
                ),
            }
        )

        cursor += size
        pattern_index += 1

    return phrases


def caption_schedule_v7(
    voice_duration: float,
):
    """
    Approximate spoken timing from word-length weights.

    This is still not forced alignment, but it is substantially
    tighter than evenly distributing captions.
    """

    phrases = caption_phrases_v7()

    if not phrases:
        return []

    usable = min(
        float(
            voice_duration
        ),
        TARGET_DURATION,
    )

    total_weight = sum(
        phrase[
            "weight"
        ]
        for phrase
        in phrases
    )

    total_weight = max(
        total_weight,
        1.0,
    )

    cursor = 0.0
    schedule = []

    for phrase in phrases:

        raw_duration = (
            usable
            * phrase[
                "weight"
            ]
            / total_weight
        )

        duration = max(
            0.32,
            min(
                1.05,
                raw_duration,
            ),
        )

        end = min(
            usable,
            cursor + duration,
        )

        if end <= cursor:
            break

        schedule.append(
            {
                "start": cursor,
                "end": end,
                "text": phrase[
                    "text"
                ],
                "emphasis": phrase[
                    "emphasis"
                ],
            }
        )

        cursor = end

        if cursor >= usable:
            break

    return schedule


############################################################
# V7 — CAPTION SAFE POSITION
############################################################

def caption_y_v7(
    source,
    optimized_moments,
    timeline_time: float,
):
    """
    Put text away from the dominant face region when possible.
    """

    elapsed = 0.0

    shot_index = 0

    for index, duration in enumerate(
        SHOT_DURATIONS
    ):

        if (
            elapsed
            <= timeline_time
            < elapsed + duration
        ):

            shot_index = index
            break

        elapsed += duration

    shot_index = min(
        shot_index,
        len(
            optimized_moments
        ) - 1,
    )

    timestamp = float(
        optimized_moments[
            shot_index
        ][
            "timestamp"
        ]
    )

    frame = source.get_frame(
        timestamp
    ).astype(
        np.uint8
    )

    faces = detect_faces(
        frame
    )

    if not faces:

        return 980

    h = frame.shape[
        0
    ]

    centers_y = [
        y + fh / 2
        for x, y, fw, fh
        in faces
    ]

    average_y = (
        float(
            np.mean(
                centers_y
            )
        )
        / h
    )

    # Face high -> caption lower.
    if average_y < 0.48:
        return 1110

    # Face low -> caption higher.
    return 760


############################################################
# V7 — SYNTHETIC IMPACT AUDIO
############################################################

def build_v7_sfx():
    """
    Generate very subtle cinematic impact pulses at major beats.

    No external copyrighted audio is needed.
    """

    import wave

    sample_rate = 44100

    duration = TARGET_DURATION

    sample_count = int(
        duration
        * sample_rate
    )

    audio = np.zeros(
        sample_count,
        dtype=np.float32,
    )

    ########################################################
    # Low ambient bed.
    ########################################################

    timeline = (
        np.arange(
            sample_count,
            dtype=np.float32,
        )
        / sample_rate
    )

    ambient = (
        np.sin(
            2
            * np.pi
            * 52.0
            * timeline
        )
        * 0.007
    )

    audio += ambient.astype(
        np.float32
    )

    ########################################################
    # Impact at selected narrative moments.
    ########################################################

    cut_times = []

    elapsed = 0.0

    for index, duration_value in enumerate(
        SHOT_DURATIONS
    ):

        if index in {
            0,
            5,
            8,
            12,
            16,
            19,
            21,
        }:

            cut_times.append(
                elapsed
            )

        elapsed += duration_value

    for hit_time in cut_times:

        start = int(
            hit_time
            * sample_rate
        )

        hit_duration = int(
            0.28
            * sample_rate
        )

        end = min(
            sample_count,
            start + hit_duration,
        )

        length = (
            end - start
        )

        if length <= 0:
            continue

        local_t = (
            np.arange(
                length,
                dtype=np.float32,
            )
            / sample_rate
        )

        envelope = np.exp(
            -local_t
            * 13.0
        )

        pulse = (
            np.sin(
                2
                * np.pi
                * 62.0
                * local_t
            )
            * envelope
            * 0.055
        )

        audio[
            start:end
        ] += pulse.astype(
            np.float32
        )

    audio = np.clip(
        audio,
        -0.15,
        0.15,
    )

    output = Path(
        "generated/audio/"
        "narrative_movie_v7_sfx.wav"
    )

    output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    pcm = (
        audio
        * 32767
    ).astype(
        np.int16
    )

    with wave.open(
        str(output),
        "wb",
    ) as wav:

        wav.setnchannels(
            1
        )

        wav.setsampwidth(
            2
        )

        wav.setframerate(
            sample_rate
        )

        wav.writeframes(
            pcm.tobytes()
        )

    return AudioFileClip(
        str(output)
    )


############################################################
# V7 — FINAL SEQUENCE QA
############################################################

def final_sequence_qa_v7(
    moments,
):
    """
    Fail loudly on obvious weak sequences.
    """

    semantic_scores = [
        float(
            moment[
                "semantic"
            ]
        )
        for moment
        in moments
    ]

    quality_scores = [
        float(
            moment[
                "quality"
            ]
        )
        for moment
        in moments
    ]

    average_semantic = float(
        np.mean(
            semantic_scores
        )
    )

    minimum_semantic = float(
        np.min(
            semantic_scores
        )
    )

    average_quality = float(
        np.mean(
            quality_scores
        )
    )

    weak_semantic_count = sum(
        score < 0.15
        for score
        in semantic_scores
    )

    print()
    print(
        "========== V7 FINAL QA =========="
    )

    print(
        "AVG SEMANTIC:",
        round(
            average_semantic,
            4,
        ),
    )

    print(
        "MIN SEMANTIC:",
        round(
            minimum_semantic,
            4,
        ),
    )

    print(
        "AVG QUALITY:",
        round(
            average_quality,
            4,
        ),
    )

    print(
        "WEAK SEMANTIC SHOTS:",
        weak_semantic_count,
    )

    if weak_semantic_count > 3:

        raise RuntimeError(
            "V7 QA rejected sequence: "
            "too many weak semantic shots."
        )

    return {
        "average_semantic": (
            average_semantic
        ),
        "minimum_semantic": (
            minimum_semantic
        ),
        "average_quality": (
            average_quality
        ),
    }


'''

text = (
    text[:position]
    + addition
    + text[position:]
)


############################################################
# HOOK RERANK INSIDE V6 OPTIMIZER
############################################################

needle = '''        if not candidates:

            raise RuntimeError(
'''

replacement = '''        if beat_index == 0:

            candidates = rerank_hook_v7(
                candidates
            )

        if not candidates:

            raise RuntimeError(
'''

if needle not in text:
    raise RuntimeError(
        "Could not patch V7 hook ranking."
    )

text = text.replace(
    needle,
    replacement,
    1,
)


############################################################
# ADD FINAL QA AFTER MOMENT OPTIMIZATION
############################################################

needle = '''    voice = build_voice(
        config
    )
'''

replacement = '''    final_sequence_qa_v7(
        optimized_moments
    )

    voice = build_voice(
        config
    )

    sfx = build_v7_sfx()
'''

if needle not in text:
    raise RuntimeError(
        "Could not patch V7 QA/audio."
    )

text = text.replace(
    needle,
    replacement,
    1,
)


############################################################
# REPLACE V6 CAPTION SCHEDULER
############################################################

text = text.replace(
    '''caption_schedule = (
                build_synced_captions_v6(
                    float(
                        voice.duration
                    )
                )
            )''',
    '''caption_schedule = (
                caption_schedule_v7(
                    float(
                        voice.duration
                    )
                )
            )''',
    1,
)


############################################################
# REPLACE CAPTION LOOP
############################################################

start = text.find(
    '''        for caption_index, (
'''
)

end = text.find(
    '''        final = CompositeVideoClip(
''',
    start,
)

if start < 0 or end < 0:
    raise RuntimeError(
        "V7 caption loop not found."
    )

new_caption_block = r'''        for caption_index, item in enumerate(
            caption_schedule
        ):

            caption_start = float(
                item[
                    "start"
                ]
            )

            caption_end = float(
                item[
                    "end"
                ]
            )

            caption_text = str(
                item[
                    "text"
                ]
            )

            emphasis = str(
                item[
                    "emphasis"
                ]
            )

            if (
                caption_end
                <= caption_start
            ):
                continue

            caption_y = caption_y_v7(
                source,
                optimized_moments,
                caption_start,
            )

            ################################################
            # Main phrase.
            ################################################

            caption = (
                TextClip(
                    text=caption_text,
                    font_size=52,
                    color="white",
                    stroke_color="black",
                    stroke_width=4,
                    method="caption",
                    size=(
                        760,
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
                        caption_y,
                    )
                )
            )

            captions.append(
                caption
            )

            ################################################
            # Keyword flash for emphasis.
            ################################################

            emphasis_duration = min(
                0.28,
                max(
                    0.16,
                    (
                        caption_end
                        - caption_start
                    )
                    * 0.34,
                ),
            )

            emphasis_clip = (
                TextClip(
                    text=emphasis,
                    font_size=59,
                    color="white",
                    stroke_color="black",
                    stroke_width=5,
                    method="caption",
                    size=(
                        700,
                        None,
                    ),
                    text_align="center",
                )
                .with_start(
                    caption_start
                )
                .with_duration(
                    emphasis_duration
                )
                .with_position(
                    (
                        "center",
                        caption_y
                        - 64,
                    )
                )
            )

            captions.append(
                emphasis_clip
            )

'''

text = (
    text[:start]
    + new_caption_block
    + text[end:]
)


############################################################
# MIX NARRATION + SUBTLE SFX
############################################################

old_audio = '''        if voice is not None:

            final = final.with_audio(
                voice
            )
'''

new_audio = '''        if voice is not None:

            mixed_audio = CompositeAudioClip(
                [
                    voice,
                    sfx,
                ]
            )

            final = final.with_audio(
                mixed_audio
            )

        else:

            mixed_audio = sfx

            final = final.with_audio(
                mixed_audio
            )
'''

if old_audio not in text:
    raise RuntimeError(
        "V7 audio block not found."
    )

text = text.replace(
    old_audio,
    new_audio,
    1,
)


############################################################
# CLEAN UP SFX / MIX OBJECTS
############################################################

needle = '''        if voice is not None:
            voice.close()
'''

replacement = '''        if voice is not None:
            voice.close()

        try:
            sfx.close()
        except Exception:
            pass

        try:
            mixed_audio.close()
        except Exception:
            pass
'''

if needle not in text:
    raise RuntimeError(
        "V7 cleanup block not found."
    )

text = text.replace(
    needle,
    replacement,
    1,
)


############################################################
# WRITE FILE
############################################################

path.write_text(
    text,
    encoding="utf-8",
)

print(
    "SUCCESS: V7 installed."
)
