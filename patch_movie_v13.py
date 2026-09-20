from pathlib import Path

path = Path(
    "render_narrative_movie_proof_v13.py"
)

text = path.read_text(
    encoding="utf-8"
)


############################################################
# IDENTITY
############################################################

text = text.replace(
    "NARRATIVE_MOVIE_REFERENCE_PROOF_V12.mp4",
    "NARRATIVE_MOVIE_REFERENCE_PROOF_V13.mp4",
)

text = text.replace(
    "narrative_movie_v12.wav",
    "narrative_movie_v13.wav",
)

text = text.replace(
    "========== RENDERING NARRATIVE V12 ==========",
    "========== RENDERING NARRATIVE V13 ==========",
)

text = text.replace(
    "========== V12 COMPLETE ==========",
    "========== V13 COMPLETE ==========",
)


############################################################
# REPLACE STATIC NARRATION WITH FALLBACK ONLY
############################################################

old_narration = '''NARRATION = (
    "At first this looks like a quiet reunion, but the city around them "
    "is already preparing for something worse. She watches him carefully "
    "as the technology comes alive. Then the scale changes. What seemed "
    "like a conversation becomes a survival problem. The machines move, "
    "the environment turns hostile, and every reaction suddenly matters. "
    "That is why the sequence works: it keeps jumping between faces, "
    "machinery and wide danger shots before the action completely takes over."
)'''

new_narration = '''NARRATION = (
    "They thought this meeting would be simple. "
    "Then the machines started waking up. "
    "Within moments, the city around them changed from a place to talk "
    "into something they had to survive. "
    "Every warning came too late. "
    "The machines kept moving, the danger kept growing, "
    "and suddenly there was nowhere left to hide. "
    "By the time the real threat appeared, running was the only choice."
)

V13_NARRATION = NARRATION
V13_STORY_SEGMENTS = []'''

if old_narration not in text:
    raise RuntimeError(
        "Could not locate original V12 NARRATION."
    )

text = text.replace(
    old_narration,
    new_narration,
    1,
)


############################################################
# INSERT V13 STORY ENGINE BEFORE V12 HOOK SYSTEM
############################################################

anchor = '''
############################################################
# V12 — SURGICAL HOOK + ENDING REFINEMENT
############################################################
'''

position = text.find(
    anchor
)

if position < 0:
    raise RuntimeError(
        "Could not locate V12 hook system."
    )


addition = r'''

############################################################
# V13 — STORY-FIRST NARRATIVE ENGINE
############################################################

V13_BANNED_META_PHRASES = (
    "wide shot",
    "reaction shot",
    "close up",
    "close-up",
    "medium shot",
    "camera",
    "footage",
    "sequence works",
    "jumping between",
    "visual beat",
    "visual beats",
    "cinematic shot",
    "establishing shot",
    "danger shots",
    "the edit",
    "editing",
)

V13_TARGET_WORDS_MIN = 72
V13_TARGET_WORDS_MAX = 94


############################################################
# STORY PHASES
############################################################

def story_phase_v13(
    beat_index,
    total,
):

    ratio = (
        beat_index
        / max(
            total - 1,
            1,
        )
    )

    if ratio < 0.14:
        return "HOOK"

    if ratio < 0.34:
        return "SETUP"

    if ratio < 0.56:
        return "COMPLICATION"

    if ratio < 0.82:
        return "ESCALATION"

    return "PAYOFF"


############################################################
# CLEAN VISUAL DESCRIPTION
############################################################

def clean_visual_description_v13(
    description,
):
    """
    Convert editor terminology into story information.

    We deliberately remove words that encourage the narrator
    to describe cinematography instead of events.
    """

    import re

    value = str(
        description
    ).lower()

    replacements = (
        ("wide cinematic", ""),
        ("cinematic", ""),
        ("establishing shot", ""),
        ("medium shot", ""),
        ("close up", ""),
        ("close-up", ""),
        ("reaction shot", ""),
        ("dramatic", ""),
        ("extreme", ""),
        ("shot", ""),
        ("visual", ""),
    )

    for old, new in replacements:

        value = value.replace(
            old,
            new,
        )

    value = re.sub(
        r"\s+",
        " ",
        value,
    ).strip()

    return value


############################################################
# EXTRACT WHAT FINAL EDIT ACTUALLY SHOWS
############################################################

def build_story_evidence_v13(
    optimized_moments,
):
    evidence = []

    total = len(
        optimized_moments
    )

    for index, moment in enumerate(
        optimized_moments
    ):

        original = (
            VISUAL_BEATS[
                index
            ]
            if index
            < len(
                VISUAL_BEATS
            )
            else "science fiction action"
        )

        evidence.append(
            {
                "beat": index + 1,
                "phase": story_phase_v13(
                    index,
                    total,
                ),
                "description":
                    clean_visual_description_v13(
                        original
                    ),
                "timestamp": float(
                    moment.get(
                        "timestamp",
                        0.0,
                    )
                ),
                "semantic": float(
                    moment.get(
                        "semantic",
                        0.0,
                    )
                ),
                "motion": float(
                    moment.get(
                        "motion",
                        0.0,
                    )
                ),
                "quality": float(
                    moment.get(
                        "v11_render_score",
                        moment.get(
                            "whole_quality",
                            0.0,
                        ),
                    )
                ),
            }
        )

    return evidence


############################################################
# COLLAPSE 22 SHOTS INTO MEANINGFUL STORY EVENTS
############################################################

def build_story_events_v13(
    evidence,
):
    """
    The edit can contain 22 shots without requiring 22
    narration statements.

    Collapse them into five story phases.
    """

    phases = (
        "HOOK",
        "SETUP",
        "COMPLICATION",
        "ESCALATION",
        "PAYOFF",
    )

    events = []

    for phase in phases:

        group = [
            item
            for item
            in evidence
            if item[
                "phase"
            ] == phase
        ]

        if not group:
            continue

        ####################################################
        # Rank the most informative descriptions.
        ####################################################

        ranked = sorted(
            group,
            key=lambda item: (
                item[
                    "semantic"
                ] * 0.38
                + item[
                    "quality"
                ] * 0.34
                + item[
                    "motion"
                ] * 0.28
            ),
            reverse=True,
        )

        descriptions = []

        for item in ranked:

            description = item[
                "description"
            ]

            if (
                description
                and description
                not in descriptions
            ):
                descriptions.append(
                    description
                )

            if len(
                descriptions
            ) >= 3:
                break

        events.append(
            {
                "phase": phase,
                "descriptions":
                    descriptions,
                "start_beat":
                    group[
                        0
                    ][
                        "beat"
                    ],
                "end_beat":
                    group[
                        -1
                    ][
                        "beat"
                    ],
            }
        )

    return events


############################################################
# LOCAL STORY GENERATOR
############################################################

def generate_story_locally_v13(
    events,
):
    """
    Deterministic fallback.

    This is intentionally story language rather than
    cinematography language.
    """

    phase_data = {
        event[
            "phase"
        ]: event
        for event
        in events
    }

    hook = (
        "They thought this meeting would be simple. "
        "They were wrong."
    )

    setup = (
        "While they try to understand each other, "
        "the technology around them begins waking up."
    )

    complication = (
        "At first it is only a warning, but the machines "
        "keep moving and the city starts turning against them."
    )

    escalation = (
        "Then the threat becomes impossible to ignore. "
        "Something much larger is coming, and every second "
        "leaves them with fewer places to escape."
    )

    payoff = (
        "When the real machine finally appears, the choice "
        "is gone. They can fight, or they can run."
    )

    ########################################################
    # Adjust wording only when corresponding phases exist.
    ########################################################

    pieces = []

    if "HOOK" in phase_data:
        pieces.append(
            hook
        )

    if "SETUP" in phase_data:
        pieces.append(
            setup
        )

    if "COMPLICATION" in phase_data:
        pieces.append(
            complication
        )

    if "ESCALATION" in phase_data:
        pieces.append(
            escalation
        )

    if "PAYOFF" in phase_data:
        pieces.append(
            payoff
        )

    return " ".join(
        pieces
    )


############################################################
# OPTIONAL OLLAMA STORY REWRITE
############################################################

def rewrite_story_with_ollama_v13(
    events,
    fallback,
):
    """
    Use the already-local Ollama installation when available.

    If Ollama is unavailable, malformed, slow, or returns weak
    narration, V13 automatically retains the deterministic
    story.
    """

    import json
    import urllib.request

    evidence_lines = []

    for event in events:

        evidence_lines.append(
            (
                event[
                    "phase"
                ]
                + ": "
                + "; ".join(
                    event[
                        "descriptions"
                    ]
                )
            )
        )

    prompt = """
You are writing narration for a 37-second vertical science-fiction short.

Tell the STORY shown by the supplied visual evidence.

STRICT RULES:
- 72 to 94 words.
- Hook immediately.
- Present tense.
- Short spoken sentences.
- Build: hook -> setup -> complication -> escalation -> payoff.
- Only state things supported by the visual evidence.
- Do not invent names.
- Do not explain filmmaking.
- Never mention shots, footage, editing, camera work, close-ups,
  wide shots, visual beats, or the fact that this is a video.
- Do not say "the sequence works".
- Do not say "watch this".
- Do not use a call to action.
- Make it sound like a human storyteller.
- End on the danger/payoff, not an explanation.

VISUAL EVIDENCE:
""" + "\n".join(
        evidence_lines
    ) + """

BASELINE STORY:
""" + fallback + """

Return ONLY the final narration.
"""

    payload = json.dumps(
        {
            "model": "qwen2.5:7b",
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.35,
                "top_p": 0.85,
            },
        }
    ).encode(
        "utf-8"
    )

    request = urllib.request.Request(
        "http://127.0.0.1:11434/api/generate",
        data=payload,
        headers={
            "Content-Type":
                "application/json"
        },
        method="POST",
    )

    try:

        with urllib.request.urlopen(
            request,
            timeout=45,
        ) as response:

            data = json.loads(
                response.read().decode(
                    "utf-8"
                )
            )

        candidate = str(
            data.get(
                "response",
                "",
            )
        ).strip()

        if candidate:
            return candidate

    except Exception as exc:

        print(
            "V13 OLLAMA:",
            "fallback narration used |",
            str(
                exc
            )[:120],
        )

    return fallback


############################################################
# STORY QA
############################################################

def story_qa_v13(
    narration,
):
    import re

    normalized = " ".join(
        str(
            narration
        ).split()
    )

    lower = normalized.lower()

    words = re.findall(
        r"[A-Za-z0-9']+",
        normalized,
    )

    banned = [
        phrase
        for phrase
        in V13_BANNED_META_PHRASES
        if phrase in lower
    ]

    sentences = [
        item.strip()
        for item
        in re.split(
            r"[.!?]+",
            normalized,
        )
        if item.strip()
    ]

    long_sentences = [
        sentence
        for sentence
        in sentences
        if len(
            sentence.split()
        ) > 23
    ]

    score = 1.0

    if len(
        words
    ) < V13_TARGET_WORDS_MIN:

        score -= min(
            0.25,
            (
                V13_TARGET_WORDS_MIN
                - len(
                    words
                )
            ) / 100.0,
        )

    if len(
        words
    ) > V13_TARGET_WORDS_MAX:

        score -= min(
            0.25,
            (
                len(
                    words
                )
                - V13_TARGET_WORDS_MAX
            ) / 100.0,
        )

    score -= (
        len(
            banned
        )
        * 0.16
    )

    score -= (
        len(
            long_sentences
        )
        * 0.06
    )

    score = max(
        0.0,
        min(
            1.0,
            score,
        ),
    )

    print()
    print(
        "========== V13 STORY QA =========="
    )

    print(
        "WORDS:",
        len(
            words
        ),
    )

    print(
        "SENTENCES:",
        len(
            sentences
        ),
    )

    print(
        "BANNED META PHRASES:",
        banned,
    )

    print(
        "OVERLONG SENTENCES:",
        len(
            long_sentences
        ),
    )

    print(
        "STORY QUALITY:",
        round(
            score,
            4,
        ),
    )

    return {
        "score": score,
        "words": len(
            words
        ),
        "banned": banned,
        "long_sentences":
            long_sentences,
    }


############################################################
# FINAL STORY BUILDER
############################################################

def build_narration_v13(
    optimized_moments,
):
    global V13_NARRATION
    global V13_STORY_SEGMENTS

    print()
    print(
        "========== V13 STORY-FIRST NARRATION =========="
    )

    evidence = (
        build_story_evidence_v13(
            optimized_moments
        )
    )

    events = (
        build_story_events_v13(
            evidence
        )
    )

    fallback = (
        generate_story_locally_v13(
            events
        )
    )

    candidate = (
        rewrite_story_with_ollama_v13(
            events,
            fallback,
        )
    )

    qa = story_qa_v13(
        candidate
    )

    ########################################################
    # Never allow a weak AI rewrite to make the final render
    # worse than the deterministic story.
    ########################################################

    if (
        qa[
            "banned"
        ]
        or qa[
            "score"
        ] < 0.78
    ):

        print(
            "V13 STORY RECOVERY:",
            "AI rewrite rejected; using grounded fallback."
        )

        candidate = fallback

        qa = story_qa_v13(
            candidate
        )

    if qa[
        "banned"
    ]:

        raise RuntimeError(
            "V13 narration still contains meta-editing language: "
            + str(
                qa[
                    "banned"
                ]
            )
        )

    V13_NARRATION = " ".join(
        candidate.split()
    )

    ########################################################
    # Save story events for diagnostics.
    ########################################################

    V13_STORY_SEGMENTS = events

    print()
    print(
        "FINAL V13 NARRATION:"
    )

    print(
        V13_NARRATION
    )

    print()
    print(
        "STORY EVENTS:"
    )

    for event in events:

        print(
            event[
                "phase"
            ],
            "| beats",
            (
                f"{event['start_beat']}"
                f"-{event['end_beat']}"
            ),
            "|",
            "; ".join(
                event[
                    "descriptions"
                ]
            ),
        )

    return V13_NARRATION


############################################################
# V13 — VISUAL / STORY STRUCTURE QA
############################################################

def visual_story_qa_v13(
    optimized_moments,
):
    print()
    print(
        "========== V13 VISUAL-STORY QA =========="
    )

    evidence = (
        build_story_evidence_v13(
            optimized_moments
        )
    )

    phases = {}

    for item in evidence:

        phases.setdefault(
            item[
                "phase"
            ],
            [],
        ).append(
            item
        )

    required = (
        "HOOK",
        "SETUP",
        "COMPLICATION",
        "ESCALATION",
        "PAYOFF",
    )

    missing = [
        phase
        for phase
        in required
        if not phases.get(
            phase
        )
    ]

    for phase in required:

        group = phases.get(
            phase,
            [],
        )

        if not group:
            continue

        avg_semantic = sum(
            item[
                "semantic"
            ]
            for item
            in group
        ) / len(
            group
        )

        avg_quality = sum(
            item[
                "quality"
            ]
            for item
            in group
        ) / len(
            group
        )

        avg_motion = sum(
            item[
                "motion"
            ]
            for item
            in group
        ) / len(
            group
        )

        print(
            phase,
            "| beats:",
            len(
                group
            ),
            "| semantic:",
            round(
                avg_semantic,
                3,
            ),
            "| quality:",
            round(
                avg_quality,
                3,
            ),
            "| motion:",
            round(
                avg_motion,
                3,
            ),
        )

    print(
        "MISSING STORY PHASES:",
        missing,
    )

    if missing:

        raise RuntimeError(
            "V13 visual story lacks phases: "
            + str(
                missing
            )
        )

    return evidence


############################################################
# V13 CAPTIONS — ALWAYS USE FINAL STORY
############################################################

def caption_chunks_v13():
    import re

    tokens = re.findall(
        r"[A-Za-z0-9']+|[,.!?;:]",
        V13_NARRATION,
    )

    chunks = []

    current = []

    strong_breaks = {
        ".",
        "!",
        "?",
        ";",
        ":",
    }

    pattern = (
        3,
        2,
        3,
        3,
        2,
    )

    pattern_index = 0

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
    # Repair isolated one-word chunks.
    ########################################################

    repaired = []

    for chunk in chunks:

        if (
            len(
                chunk.split()
            ) == 1
            and repaired
            and len(
                repaired[
                    -1
                ].split()
            ) <= 2
        ):

            repaired[
                -1
            ] += (
                " "
                + chunk
            )

        else:

            repaired.append(
                chunk
            )

    return repaired


def caption_schedule_v13(
    voice_duration,
):
    chunks = (
        caption_chunks_v13()
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

        weights.append(
            sum(
                0.72
                + min(
                    len(
                        word
                    ),
                    11,
                ) / 6.8
                for word
                in words
            )
        )

    total = max(
        float(
            sum(
                weights
            )
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

    ########################################################
    # Reuse V12's real Piper WAV energy alignment.
    ########################################################

    energy_data = (
        speech_energy_v12()
    )

    aligned = [
        0.0
    ]

    for boundary in boundaries[
        1:-1
    ]:

        aligned.append(
            snap_to_speech_pause_v12(
                boundary,
                energy_data,
            )
        )

    aligned.append(
        usable
    )

    ########################################################
    # Monotonic cleanup.
    ########################################################

    cleaned = [
        0.0
    ]

    minimum = 0.20

    for boundary in aligned[
        1:
    ]:

        value = max(
            float(
                boundary
            ),
            cleaned[
                -1
            ]
            + minimum,
        )

        value = min(
            value,
            usable,
        )

        cleaned.append(
            value
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


'''

text = (
    text[:position]
    + addition
    + text[position:]
)


############################################################
# BUILD FINAL STORY AFTER FINAL VISUAL SEQUENCE
############################################################

old = '''    final_presentation_qa_v12(
        optimized_moments
    )

    voice = build_voice(
        config
    )
'''

new = '''    final_presentation_qa_v12(
        optimized_moments
    )

    visual_story_qa_v13(
        optimized_moments
    )

    build_narration_v13(
        optimized_moments
    )

    voice = build_voice(
        config,
        narration=V13_NARRATION,
    )
'''

if old not in text:
    raise RuntimeError(
        "Could not wire V13 story builder into main()."
    )

text = text.replace(
    old,
    new,
    1,
)


############################################################
# BUILD_VOICE MUST ACCEPT FINAL STORY
############################################################

old = '''def build_voice(
    config,
):'''

new = '''def build_voice(
    config,
    narration=None,
):

    if narration is None:
        narration = V13_NARRATION'''

if old not in text:
    raise RuntimeError(
        "Could not patch build_voice signature."
    )

text = text.replace(
    old,
    new,
    1,
)


############################################################
# SEND FINAL V13 STORY TO PIPER
############################################################

old = '''        input=NARRATION,
        text=True,
        capture_output=True,
'''

new = '''        input=narration,
        text=True,
        capture_output=True,
'''

if old not in text:
    raise RuntimeError(
        "Could not patch Piper narration input."
    )

text = text.replace(
    old,
    new,
    1,
)


############################################################
# USE V13 CAPTIONS
############################################################

old = '''caption_schedule_v12(
                    float(
                        voice.duration
                    )
                )'''

new = '''caption_schedule_v13(
                    float(
                        voice.duration
                    )
                )'''

if old not in text:
    raise RuntimeError(
        "Could not locate V12 caption scheduler call."
    )

text = text.replace(
    old,
    new,
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
    "SUCCESS: V13 story-first narrative engine installed."
)
