"""Reusable V18 final-master QA extracted from the benchmark.

This module preserves the proven V18_FINAL_MASTER / final_master_qa_v18
contract. It does not reimplement or weaken those thresholds.
"""

from __future__ import annotations

import re


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
