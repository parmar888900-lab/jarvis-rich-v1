from pathlib import Path
import py_compile
import shutil
import sys

SOURCE = Path("render_narrative_movie_proof_v15.py")
BACKUP = Path(
    "render_narrative_movie_proof_v15_before_safe_install.py"
)

print()
print("========== V15 PYTHON PATCHER ==========")

text = SOURCE.read_text(
    encoding="utf-8"
)

# ------------------------------------------------------------
# SAFETY
# ------------------------------------------------------------

if "V15_PIPELINE_WIRING_INSTALLED = True" in text:
    print("V15 is already installed.")
    sys.exit(0)

required = [
    "def build_narration_v13(",
    "def build_voice(",
    "def main():",
    "def continuity_qa_v14(",
    "def final_presentation_qa_v12(",
]

missing = [
    item
    for item in required
    if item not in text
]

if missing:
    raise RuntimeError(
        "Required V14/V13 structures missing: "
        + repr(missing)
    )

# ------------------------------------------------------------
# V15 ENGINE
# ------------------------------------------------------------

engine = r'''

############################################################
# V15 — STORY / VIEWER CONTRACT ENGINE
############################################################

V15_PIPELINE_WIRING_INSTALLED = True


def build_source_event_graph_v15(
    moments,
):
    graph = []

    total = len(moments)

    for index, moment in enumerate(moments):

        if index == 0:
            phase = "HOOK"

        elif index < max(
            2,
            int(total * 0.25),
        ):
            phase = "SETUP"

        elif index < max(
            3,
            int(total * 0.50),
        ):
            phase = "COMPLICATION"

        elif index < max(
            4,
            int(total * 0.82),
        ):
            phase = "ESCALATION"

        else:
            phase = "PAYOFF"

        description = (
            VISUAL_BEATS[index]
            if index < len(VISUAL_BEATS)
            else "science fiction action"
        )

        graph.append(
            {
                "beat": index + 1,
                "phase": phase,
                "description": description,
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
                "render": float(
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

    return graph


def sequence_continuity_score_v15(
    graph,
):
    if len(graph) < 2:
        return 1.0, []

    backward = []
    penalty = 0.0

    for index in range(
        1,
        len(graph),
    ):
        delta = (
            graph[index]["timestamp"]
            - graph[index - 1]["timestamp"]
        )

        if delta < 0.0:

            magnitude = abs(delta)

            penalty += min(
                0.18,
                magnitude / 500.0,
            )

            if magnitude > 45.0:
                backward.append(
                    (
                        index + 1,
                        round(
                            delta,
                            2,
                        ),
                    )
                )

    return (
        max(
            0.0,
            1.0 - penalty,
        ),
        backward,
    )


def hook_contract_v15(
    graph,
):
    if not graph:
        return {
            "score": 0.0,
            "safe": False,
            "opening_delta": 0.0,
        }

    hook = graph[0]

    if len(graph) > 1:
        opening_delta = (
            graph[1]["timestamp"]
            - hook["timestamp"]
        )
    else:
        opening_delta = 0.0

    safe = (
        opening_delta >= -45.0
    )

    score = (
        hook["render"] * 0.35
        + hook["motion"] * 0.30
        + hook["semantic"] * 0.20
        + (
            0.15
            if safe
            else 0.0
        )
    )

    return {
        "score": max(
            0.0,
            min(
                1.0,
                score,
            ),
        ),
        "safe": safe,
        "opening_delta":
            opening_delta,
    }


def payoff_contract_v15(
    graph,
):
    if not graph:
        return {
            "score": 0.0,
        }

    ending = graph[-1]

    score = (
        ending["render"] * 0.36
        + ending["motion"] * 0.34
        + ending["semantic"] * 0.20
        + 0.10
    )

    return {
        "score": max(
            0.0,
            min(
                1.0,
                score,
            ),
        )
    }


def claim_evidence_contract_v15(
    narration,
    graph,
):
    import re

    text = " ".join(
        str(narration).split()
    )

    lower = text.lower()

    dangerous_claims = (
        "nowhere left to hide",
        "running was the only choice",
        "they knew",
        "they thought",
        "they realized",
        "they planned",
        "they wanted",
        "they decided",
        "too late",
        "had no choice",
    )

    unsupported = [
        phrase
        for phrase in dangerous_claims
        if phrase in lower
    ]

    visual_text = " ".join(
        node["description"]
        for node in graph
    ).lower()

    evidence_words = set(
        re.findall(
            r"[a-z]+",
            visual_text,
        )
    )

    narration_words = set(
        re.findall(
            r"[a-z]+",
            lower,
        )
    )

    useful = {
        word
        for word in evidence_words
        if len(word) >= 5
    }

    if useful:

        overlap = len(
            useful
            & narration_words
        )

        lexical_support = min(
            1.0,
            0.55
            + overlap
            / max(
                len(useful),
                1,
            ),
        )

    else:
        lexical_support = 1.0

    score = max(
        0.0,
        min(
            1.0,
            lexical_support
            - len(unsupported) * 0.12,
        ),
    )

    return {
        "score": score,
        "unsupported":
            unsupported,
    }


def repair_unsupported_story_v15(
    narration,
):
    text = " ".join(
        str(narration).split()
    )

    replacements = (
        (
            "there was nowhere left to hide",
            "the danger keeps growing",
        ),
        (
            "There was nowhere left to hide",
            "The danger keeps growing",
        ),
        (
            "running was the only choice",
            "the machines keep moving closer",
        ),
        (
            "Running was the only choice",
            "The machines keep moving closer",
        ),
    )

    for old, new in replacements:
        text = text.replace(
            old,
            new,
        )

    return text


def narration_visual_alignment_v15(
    narration,
    graph,
):
    import re

    narration_words = set(
        re.findall(
            r"[a-z]+",
            str(narration).lower(),
        )
    )

    phases = (
        "HOOK",
        "SETUP",
        "COMPLICATION",
        "ESCALATION",
        "PAYOFF",
    )

    phase_scores = {}

    for phase in phases:

        descriptions = " ".join(
            node["description"]
            for node in graph
            if node["phase"] == phase
        ).lower()

        words = {
            word
            for word in re.findall(
                r"[a-z]+",
                descriptions,
            )
            if len(word) > 4
        }

        if not words:
            score = 1.0

        else:
            overlap = len(
                words
                & narration_words
            )

            score = min(
                1.0,
                0.50
                + overlap
                / max(
                    len(words),
                    1,
                ),
            )

        phase_scores[phase] = score

    average = (
        sum(
            phase_scores.values()
        )
        / len(
            phase_scores
        )
    )

    return average, phase_scores


def caption_grammar_qa_v15(
    narration,
):
    import re

    text = " ".join(
        str(narration).split()
    )

    sentences = [
        sentence.strip()
        for sentence in re.split(
            r"(?<=[.!?])\s+",
            text,
        )
        if sentence.strip()
    ]

    overlong = []

    for index, sentence in enumerate(
        sentences
    ):

        words = len(
            sentence.split()
        )

        if words > 18:
            overlong.append(
                (
                    index + 1,
                    words,
                )
            )

    dangling = bool(
        re.search(
            r"\b(and|but|because|with|to|the)$",
            text.lower(),
        )
    )

    score = 1.0

    score -= (
        len(overlong) * 0.06
    )

    if dangling:
        score -= 0.15

    return {
        "score": max(
            0.0,
            score,
        ),
        "overlong":
            overlong,
        "dangling":
            dangling,
    }


def enforce_story_contract_v15(
    narration,
    moments,
):
    graph = (
        build_source_event_graph_v15(
            moments
        )
    )

    original = " ".join(
        str(narration).split()
    )

    before = (
        claim_evidence_contract_v15(
            original,
            graph,
        )
    )

    repaired = (
        repair_unsupported_story_v15(
            original
        )
    )

    after = (
        claim_evidence_contract_v15(
            repaired,
            graph,
        )
    )

    if (
        after["score"]
        >= before["score"]
    ):
        final_story = repaired
    else:
        final_story = original

    print()
    print(
        "========== V15 STORY CONTRACT =========="
    )

    print(
        "BEFORE:",
        round(
            before["score"],
            4,
        ),
        "| unsupported:",
        before["unsupported"],
    )

    print(
        "AFTER:",
        round(
            after["score"],
            4,
        ),
        "| unsupported:",
        after["unsupported"],
    )

    print()
    print(
        "FINAL V15 NARRATION:"
    )
    print(
        final_story
    )

    return final_story


def final_viewer_qa_v15(
    moments,
    narration,
):
    print()
    print(
        "========== V15 FINAL VIEWER QA =========="
    )

    graph = (
        build_source_event_graph_v15(
            moments
        )
    )

    continuity, severe = (
        sequence_continuity_score_v15(
            graph
        )
    )

    hook = hook_contract_v15(
        graph
    )

    payoff = payoff_contract_v15(
        graph
    )

    claims = (
        claim_evidence_contract_v15(
            narration,
            graph,
        )
    )

    alignment, phases = (
        narration_visual_alignment_v15(
            narration,
            graph,
        )
    )

    captions = (
        caption_grammar_qa_v15(
            narration
        )
    )

    average_render = sum(
        node["render"]
        for node in graph
    ) / max(
        len(graph),
        1,
    )

    average_semantic = sum(
        node["semantic"]
        for node in graph
    ) / max(
        len(graph),
        1,
    )

    average_motion = sum(
        node["motion"]
        for node in graph
    ) / max(
        len(graph),
        1,
    )

    viewer_score = (
        average_render * 0.16
        + average_semantic * 0.10
        + average_motion * 0.08
        + continuity * 0.18
        + hook["score"] * 0.13
        + payoff["score"] * 0.12
        + claims["score"] * 0.11
        + alignment * 0.07
        + captions["score"] * 0.05
    )

    presentation = min(
        10.0,
        max(
            0.0,
            4.0
            + viewer_score * 7.0,
        ),
    )

    print(
        "AVG RENDER:",
        round(
            average_render,
            4,
        )
    )

    print(
        "AVG SEMANTIC:",
        round(
            average_semantic,
            4,
        )
    )

    print(
        "AVG MOTION:",
        round(
            average_motion,
            4,
        )
    )

    print(
        "CONTINUITY:",
        round(
            continuity,
            4,
        )
    )

    print(
        "HOOK CONTRACT:",
        round(
            hook["score"],
            4,
        ),
        "| opening delta:",
        round(
            hook["opening_delta"],
            2,
        ),
        "sec",
    )

    print(
        "PAYOFF CONTRACT:",
        round(
            payoff["score"],
            4,
        )
    )

    print(
        "CLAIM SUPPORT:",
        round(
            claims["score"],
            4,
        )
    )

    print(
        "UNSUPPORTED CLAIMS:",
        claims["unsupported"],
    )

    print(
        "NARRATION / VISUAL:",
        round(
            alignment,
            4,
        )
    )

    print(
        "PHASE ALIGNMENT:",
        {
            key: round(
                value,
                3,
            )
            for key, value
            in phases.items()
        },
    )

    print(
        "CAPTION GRAMMAR:",
        round(
            captions["score"],
            4,
        )
    )

    print(
        "V15 VIEWER SCORE:",
        round(
            presentation,
            2,
        ),
        "/ 10",
    )

    failures = []

    if not hook["safe"]:
        failures.append(
            "unsafe opening chronology"
        )

    if severe:
        failures.append(
            "major temporal rewind"
        )

    if claims["unsupported"]:
        failures.append(
            "unsupported narration claims"
        )

    if claims["score"] < 0.58:
        failures.append(
            "weak claim grounding"
        )

    if alignment < 0.50:
        failures.append(
            "weak narration/visual alignment"
        )

    if captions["score"] < 0.70:
        failures.append(
            "caption grammar"
        )

    if failures:

        print(
            "V15 HARD FAILURES:",
            failures,
        )

        return {
            "passed": False,
            "score": presentation,
            "failures": failures,
        }

    print(
        "V15 VIEWER GATE: PASS"
    )

    return {
        "passed": True,
        "score": presentation,
        "failures": [],
    }

'''

# ------------------------------------------------------------
# INSERT ENGINE BEFORE BUILD_VOICE
# ------------------------------------------------------------

voice_anchor = "\ndef build_voice(\n"

if voice_anchor not in text:
    raise RuntimeError(
        "Could not locate build_voice anchor."
    )

text = text.replace(
    voice_anchor,
    engine + voice_anchor,
    1,
)

# ------------------------------------------------------------
# WIRE STORY CONTRACT
# ------------------------------------------------------------

narration_call = '''    build_narration_v13(
        optimized_moments
    )
'''

if narration_call not in text:
    raise RuntimeError(
        "Could not locate build_narration_v13 call in main."
    )

story_wire = narration_call + '''

    ########################################################
    # V15 — CLAIM / EVIDENCE STORY CONTRACT
    ########################################################

    V13_NARRATION = enforce_story_contract_v15(
        V13_NARRATION,
        optimized_moments,
    )
'''

text = text.replace(
    narration_call,
    story_wire,
    1,
)

# ------------------------------------------------------------
# WIRE VIEWER QA BEFORE VOICE / ENCODING
# ------------------------------------------------------------

voice_call = '''    voice = build_voice(
        config,
        narration=V13_NARRATION,
    )
'''

if voice_call not in text:
    raise RuntimeError(
        "Could not locate build_voice call in main."
    )

viewer_wire = '''

    ########################################################
    # V15 — FINAL PRE-RENDER VIEWER GATE
    ########################################################

    v15_viewer_result = final_viewer_qa_v15(
        optimized_moments,
        V13_NARRATION,
    )

    if not v15_viewer_result["passed"]:

        raise RuntimeError(
            "V15 viewer QA rejected the edit before encoding. "
            "Failures: "
            + str(
                v15_viewer_result[
                    "failures"
                ]
            )
        )

'''

text = text.replace(
    voice_call,
    viewer_wire + voice_call,
    1,
)

# ------------------------------------------------------------
# WRITE
# ------------------------------------------------------------

SOURCE.write_text(
    text,
    encoding="utf-8",
)

# ------------------------------------------------------------
# COMPILE — RESTORE AUTOMATICALLY IF BROKEN
# ------------------------------------------------------------

try:

    py_compile.compile(
        str(SOURCE),
        doraise=True,
    )

except Exception:

    print()
    print(
        "COMPILE FAILED — RESTORING BACKUP"
    )

    shutil.copy2(
        BACKUP,
        SOURCE,
    )

    raise

print(
    "COMPILE: OK"
)

# ------------------------------------------------------------
# VERIFY
# ------------------------------------------------------------

verify = SOURCE.read_text(
    encoding="utf-8"
)

checks = {
    "V15 marker":
        "V15_PIPELINE_WIRING_INSTALLED = True"
        in verify,

    "Source event graph":
        "def build_source_event_graph_v15("
        in verify,

    "Continuity contract":
        "def sequence_continuity_score_v15("
        in verify,

    "Hook contract":
        "def hook_contract_v15("
        in verify,

    "Payoff contract":
        "def payoff_contract_v15("
        in verify,

    "Claim evidence":
        "def claim_evidence_contract_v15("
        in verify,

    "Story repair":
        "def repair_unsupported_story_v15("
        in verify,

    "Narration alignment":
        "def narration_visual_alignment_v15("
        in verify,

    "Caption QA":
        "def caption_grammar_qa_v15("
        in verify,

    "Viewer QA":
        "def final_viewer_qa_v15("
        in verify,

    "Story contract wired":
        "V13_NARRATION = enforce_story_contract_v15("
        in verify,

    "Viewer gate wired":
        "v15_viewer_result = final_viewer_qa_v15("
        in verify,

    "V14 continuity preserved":
        "def continuity_qa_v14("
        in verify,

    "V14 repair preserved":
        "def repair_major_story_jumps_v14("
        in verify,
}

print()
print(
    "========== V15 VERIFICATION =========="
)

for name, passed in checks.items():

    print(
        (
            "[PASS]"
            if passed
            else "[FAIL]"
        ),
        name,
    )

failed = [
    name
    for name, passed
    in checks.items()
    if not passed
]

if failed:

    shutil.copy2(
        BACKUP,
        SOURCE,
    )

    raise RuntimeError(
        "V15 verification failed and backup "
        "was restored: "
        + repr(failed)
    )

print()
print(
    "======================================================"
)
print(
    " V15 ENGINE INSTALLED"
)
print(
    " COMPILE: OK"
)
print(
    " STRUCTURAL QA: PASSED"
)
print(
    " RENDER: NOT STARTED"
)
print(
    "======================================================"
)

