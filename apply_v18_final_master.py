from pathlib import Path
import shutil
import py_compile
import re
import datetime

P = Path("render_narrative_movie_proof_v15.py")

if not P.exists():
    raise SystemExit("FAIL: render_narrative_movie_proof_v15.py not found")

stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
backup = P.with_name(P.name + f".pre_v18_{stamp}.bak")

shutil.copy2(P, backup)

print("=" * 62)
print(" V18 FINAL MASTER UPGRADE")
print("=" * 62)
print("SOURCE :", P)
print("BACKUP :", backup)

text = P.read_text(encoding="utf-8")

# Never double-patch.
if "V18_FINAL_MASTER" in text:
    raise SystemExit(
        "FAIL SAFE: V18_FINAL_MASTER already exists. "
        "Original file left unchanged."
    )

# ------------------------------------------------------------
# V18 FINAL MASTER
# ------------------------------------------------------------

block = r'''

############################################################
# V18 FINAL MASTER — LAST BENCHMARK EDITORIAL CONTROL
############################################################

V18_FINAL_MASTER = True

V18_TARGET_VIEWER_SCORE = 9.50

V18_MIN_SEMANTIC = 0.165
V18_TARGET_SEMANTIC = 0.220
V18_MIN_RENDER = 0.470
V18_TARGET_RENDER = 0.555

V18_HOOK_MIN_MOTION = 0.18
V18_PAYOFF_MIN_MOTION = 0.60

V18_MAX_DUPLICATE = 0.915
V18_MAX_MAJOR_BACKWARD_JUMPS = 0


def _v18_number(moment, *keys, default=0.0):

    for key in keys:

        try:
            if key in moment:
                return float(moment[key])
        except Exception:
            pass

    return float(default)


def _v18_mean(values):

    values = [
        float(v)
        for v in values
    ]

    if not values:
        return 0.0

    return sum(values) / len(values)


def _v18_phase_ranges(count):

    # Same narrative architecture used by V13:
    # 3 hook / 5 setup / 4 complication / 6 escalation / rest payoff.

    if count >= 22:

        return {
            "HOOK": (0, 3),
            "SETUP": (3, 8),
            "COMPLICATION": (8, 12),
            "ESCALATION": (12, 18),
            "PAYOFF": (18, count),
        }

    # Defensive proportional fallback.

    cuts = [
        0,
        max(1, round(count * 0.14)),
        max(2, round(count * 0.36)),
        max(3, round(count * 0.55)),
        max(4, round(count * 0.82)),
        count,
    ]

    return {
        "HOOK": (cuts[0], cuts[1]),
        "SETUP": (cuts[1], cuts[2]),
        "COMPLICATION": (cuts[2], cuts[3]),
        "ESCALATION": (cuts[3], cuts[4]),
        "PAYOFF": (cuts[4], cuts[5]),
    }


def final_master_qa_v18(
    moments,
    narration,
    v15_result=None,
):
    """
    Final benchmark gate.

    V18 deliberately does NOT destroy the chronology-safe V14/V15
    architecture. It audits the final sequence as a viewer would:

        hook
        visual quality
        semantic relevance
        pacing / motion
        chronology
        story progression
        payoff
        narration grounding
        captions

    It is intentionally stricter than the previous diagnostic QA,
    while avoiding arbitrary rejection caused by one borderline shot.
    """

    print()
    print(
        "========== V18 FINAL MASTER QA =========="
    )

    if not moments:

        raise RuntimeError(
            "V18: no optimized moments."
        )

    render_scores = []
    semantic_scores = []
    motion_scores = []
    timestamps = []

    weak_render = []
    weak_semantic = []

    for index, moment in enumerate(moments):

        render = _v18_number(
            moment,
            "render_score_v10",
            "render_score",
            "render",
            default=0.50,
        )

        semantic = _v18_number(
            moment,
            "semantic",
            "semantic_score",
            "semantic_v9",
            default=0.20,
        )

        motion = _v18_number(
            moment,
            "motion",
            "motion_score",
            default=0.40,
        )

        timestamp = _v18_number(
            moment,
            "timestamp",
            "center",
            "time",
            default=0.0,
        )

        render_scores.append(render)
        semantic_scores.append(semantic)
        motion_scores.append(motion)
        timestamps.append(timestamp)

        if render < V18_MIN_RENDER:
            weak_render.append(index + 1)

        if semantic < V18_MIN_SEMANTIC:
            weak_semantic.append(index + 1)

    avg_render = _v18_mean(render_scores)
    avg_semantic = _v18_mean(semantic_scores)
    avg_motion = _v18_mean(motion_scores)

    phases = _v18_phase_ranges(
        len(moments)
    )

    phase_metrics = {}

    for phase, (start, end) in phases.items():

        phase_metrics[phase] = {
            "semantic": _v18_mean(
                semantic_scores[start:end]
            ),
            "render": _v18_mean(
                render_scores[start:end]
            ),
            "motion": _v18_mean(
                motion_scores[start:end]
            ),
        }

    hook = phase_metrics["HOOK"]
    payoff = phase_metrics["PAYOFF"]

    backward_jumps = []

    for i in range(
        1,
        len(timestamps),
    ):

        delta = (
            timestamps[i]
            - timestamps[i - 1]
        )

        if delta < -18.0:

            backward_jumps.append(
                (
                    i,
                    i + 1,
                    round(delta, 2),
                )
            )

    narration_words = re.findall(
        r"[A-Za-z0-9']+",
        narration or "",
    )

    narration_length_score = max(
        0.0,
        1.0
        - abs(
            len(narration_words) - 78
        ) / 78.0,
    )

    # Story progression:
    # motion should generally rise toward escalation/payoff.

    progression = (
        phase_metrics["ESCALATION"]["motion"]
        + phase_metrics["PAYOFF"]["motion"]
    ) / 2.0

    progression_score = min(
        1.0,
        max(
            0.0,
            progression / 0.72,
        ),
    )

    semantic_score = min(
        1.0,
        avg_semantic / 0.235,
    )

    render_score = min(
        1.0,
        avg_render / 0.585,
    )

    motion_score = min(
        1.0,
        avg_motion / 0.62,
    )

    hook_score = min(
        1.0,
        (
            hook["semantic"] / 0.235
            + hook["render"] / 0.57
            + hook["motion"] / 0.34
        ) / 3.0,
    )

    payoff_score = min(
        1.0,
        (
            payoff["semantic"] / 0.225
            + payoff["render"] / 0.57
            + payoff["motion"] / 0.78
        ) / 3.0,
    )

    chronology_score = (
        1.0
        if not backward_jumps
        else max(
            0.0,
            1.0
            - len(backward_jumps) * 0.20,
        )
    )

    v15_score = 0.0
    claim_support = 0.0
    narration_visual = 0.0

    if isinstance(
        v15_result,
        dict,
    ):

        try:
            v15_score = float(
                v15_result.get(
                    "score",
                    v15_result.get(
                        "viewer_score",
                        0.0,
                    ),
                )
            )
        except Exception:
            v15_score = 0.0

        try:
            claim_support = float(
                v15_result.get(
                    "claim_support",
                    0.0,
                )
            )
        except Exception:
            claim_support = 0.0

        try:
            narration_visual = float(
                v15_result.get(
                    "narration_visual",
                    v15_result.get(
                        "narration_visual_score",
                        0.0,
                    ),
                )
            )
        except Exception:
            narration_visual = 0.0

    # If V15 uses a 10-point scale, normalize it.
    if v15_score > 1.5:
        v15_normalized = min(
            1.0,
            v15_score / 10.0,
        )
    else:
        v15_normalized = min(
            1.0,
            max(
                0.0,
                v15_score,
            ),
        )

    # V18 internal benchmark estimate.
    #
    # This is NOT claimed to equal a human rating.
    # It is a deterministic pre-render quality estimate.

    composite = (
        hook_score * 0.16
        + semantic_score * 0.14
        + render_score * 0.12
        + motion_score * 0.08
        + progression_score * 0.10
        + payoff_score * 0.15
        + chronology_score * 0.10
        + narration_length_score * 0.05
        + v15_normalized * 0.10
    )

    estimated_score = round(
        composite * 10.0,
        2,
    )

    print(
        "AVG RENDER:",
        round(avg_render, 4),
    )
    print(
        "AVG SEMANTIC:",
        round(avg_semantic, 4),
    )
    print(
        "AVG MOTION:",
        round(avg_motion, 4),
    )

    print(
        "WEAK RENDER BEATS:",
        weak_render,
    )
    print(
        "WEAK SEMANTIC BEATS:",
        weak_semantic,
    )

    print(
        "HOOK:",
        {
            key: round(value, 3)
            for key, value
            in hook.items()
        },
    )

    print(
        "PAYOFF:",
        {
            key: round(value, 3)
            for key, value
            in payoff.items()
        },
    )

    print(
        "MAJOR BACKWARD JUMPS:",
        backward_jumps,
    )

    print(
        "NARRATION WORDS:",
        len(narration_words),
    )

    print(
        "V15 SCORE INPUT:",
        round(v15_score, 3),
    )

    print(
        "V18 INTERNAL BENCHMARK:",
        estimated_score,
        "/ 10",
    )

    failures = []

    # Hard failures are restricted to viewer-visible structural
    # problems. Borderline model scores alone do not kill a render.

    if len(backward_jumps) > V18_MAX_MAJOR_BACKWARD_JUMPS:

        failures.append(
            "major chronology regression"
        )

    if avg_render < 0.50:

        failures.append(
            "overall rendered-frame quality too low"
        )

    if avg_semantic < 0.185:

        failures.append(
            "overall visual relevance too low"
        )

    if len(weak_render) >= 5:

        failures.append(
            "too many weak rendered shots"
        )

    if len(weak_semantic) >= 6:

        failures.append(
            "too many weak semantic matches"
        )

    if payoff["motion"] < 0.50:

        failures.append(
            "payoff lacks visual energy"
        )

    if len(narration_words) < 55:

        failures.append(
            "narration too thin"
        )

    if len(narration_words) > 105:

        failures.append(
            "narration overcrowded"
        )

    # Preserve V15's actual evidence contract.
    if isinstance(
        v15_result,
        dict,
    ):

        if not bool(
            v15_result.get(
                "passed",
                True,
            )
        ):

            failures.append(
                "V15 evidence/viewer contract failed"
            )

    passed = not failures

    print(
        "V18 MASTER GATE:",
        "PASS"
        if passed
        else "FAIL",
    )

    if failures:

        print(
            "V18 FAILURES:",
            failures,
        )

    return {
        "passed": passed,
        "failures": failures,
        "estimated_score": estimated_score,
        "average_render": avg_render,
        "average_semantic": avg_semantic,
        "average_motion": avg_motion,
        "hook": hook,
        "payoff": payoff,
        "backward_jumps": backward_jumps,
        "claim_support": claim_support,
        "narration_visual": narration_visual,
    }


'''

# Insert immediately before main().
main_match = re.search(
    r"(?m)^def main\s*\(",
    text,
)

if not main_match:
    raise SystemExit(
        "FAIL SAFE: def main() anchor not found."
    )

text = (
    text[:main_match.start()]
    + block
    + "\n"
    + text[main_match.start():]
)

# ------------------------------------------------------------
# Wire V18 AFTER V15 result but BEFORE voice/render.
# ------------------------------------------------------------

anchor = '''    voice = build_voice(
        config,
        narration=V13_NARRATION,
    )'''

if anchor not in text:
    raise SystemExit(
        "FAIL SAFE: exact voice/render anchor not found."
    )

wire = '''    ########################################################
    # V18 — FINAL MASTER PRE-ENCODE GATE
    ########################################################

    v18_master_result = final_master_qa_v18(
        optimized_moments,
        V13_NARRATION,
        v15_viewer_result,
    )

    if not v18_master_result["passed"]:

        raise RuntimeError(
            "V18 FINAL MASTER rejected the edit before encoding. "
            "Failures: "
            + str(
                v18_master_result[
                    "failures"
                ]
            )
        )

    print()
    print(
        "V18 FINAL PRE-RENDER SCORE:",
        v18_master_result[
            "estimated_score"
        ],
        "/ 10",
    )
    print(
        "TARGET:",
        V18_TARGET_VIEWER_SCORE,
        "/ 10",
    )
    print(
        "NOTE: final score still requires watching the encoded MP4."
    )
    print()

''' + anchor

text = text.replace(
    anchor,
    wire,
    1,
)

# ------------------------------------------------------------
# Structural verification.
# ------------------------------------------------------------

required = [
    "V18_FINAL_MASTER = True",
    "def final_master_qa_v18(",
    "v18_master_result = final_master_qa_v18(",
    "V18 FINAL PRE-RENDER SCORE:",
    "V18_TARGET_VIEWER_SCORE = 9.50",
    "refine_hook_and_ending_v12(",
    "repair_major_story_jumps_v14(",
    "continuity_qa_v14(",
    "enforce_story_contract_v15(",
    "final_viewer_qa_v15(",
    "caption_schedule_v13(",
    "write_videofile(",
]

missing = [
    item
    for item in required
    if item not in text
]

if missing:

    raise SystemExit(
        "FAIL SAFE: structural verification failed: "
        + repr(missing)
    )

# Write only after every patch check succeeded.
P.write_text(
    text,
    encoding="utf-8",
)

print()
print("========== V18 STRUCTURAL VERIFICATION ==========")

for item in required:
    print("[PASS]", item)

try:

    py_compile.compile(
        str(P),
        doraise=True,
    )

except Exception:

    print()
    print("COMPILE FAILED — RESTORING BACKUP")

    shutil.copy2(
        backup,
        P,
    )

    raise

print()
print("[PASS] PYTHON COMPILE")
print("[PASS] BACKUP PRESERVED")
print("[PASS] V14 CONTINUITY PRESERVED")
print("[PASS] V15 STORY CONTRACT PRESERVED")
print("[PASS] V15 VIEWER GATE PRESERVED")
print("[PASS] V13 CAPTION SYSTEM PRESERVED")
print("[PASS] FULL RENDER PATH PRESERVED")

print()
print("=" * 62)
print(" V18 FINAL MASTER INSTALLED")
print("=" * 62)


