from pathlib import Path
import py_compile
import shutil
import sys

path = Path("render_narrative_movie_proof_v15.py")
backup = Path(
    "render_narrative_movie_proof_v15_before_v15_1_ending_chronology.py"
)

text = path.read_text(encoding="utf-8")

MARKER = "V15_1_ENDING_CHRONOLOGY_GUARD"

if MARKER in text:
    print("V15.1 ending chronology guard already installed.")
    py_compile.compile(str(path), doraise=True)
    print("COMPILE: OK")
    sys.exit(0)

old = '''    previous = output[-2]

    best_end = output[-1]
    best_end_score = -999.0

    for candidate in pools[-1]:

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

        similarity_previous = float(
            (
                candidate["embedding"]
                @ previous["embedding"]
            ).item()
        )

        repetition_penalty = max(
            0.0,
            similarity_previous - 0.91,
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

    output[-1] = best_end
'''

new = '''    previous = output[-2]

    ########################################################
    # V15_1_ENDING_CHRONOLOGY_GUARD
    #
    # The final shot must behave like an ending, not like a
    # visually strong flashback.
    #
    # Prefer candidates at/after the previous story beat.
    # A tiny rewind is tolerated for editorial flexibility.
    ########################################################

    previous_time = float(
        previous.get(
            "timestamp",
            0.0,
        )
    )

    ENDING_REWIND_TOLERANCE = 5.0

    scored_endings = []

    for candidate in pools[-1]:

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

        timestamp = float(
            candidate.get(
                "timestamp",
                0.0,
            )
        )

        ending_delta = (
            timestamp
            - previous_time
        )

        rewind = max(
            0.0,
            -ending_delta,
        )

        similarity_previous = float(
            (
                candidate["embedding"]
                @ previous["embedding"]
            ).item()
        )

        repetition_penalty = max(
            0.0,
            similarity_previous - 0.91,
        ) * 0.65

        ####################################################
        # Chronology penalty.
        #
        # <= 5 sec:
        #     normal editorial tolerance
        #
        # > 5 sec:
        #     increasingly expensive
        #
        # A 62.8 sec rewind can no longer win merely because
        # the candidate has high motion.
        ####################################################

        if rewind <= ENDING_REWIND_TOLERANCE:

            chronology_penalty = 0.0

        elif rewind <= 20.0:

            chronology_penalty = (
                0.10
                + (
                    rewind
                    - ENDING_REWIND_TOLERANCE
                )
                / 15.0
                * 0.20
            )

        elif rewind <= 45.0:

            chronology_penalty = (
                0.30
                + (
                    rewind - 20.0
                )
                / 25.0
                * 0.35
            )

        else:

            chronology_penalty = (
                0.65
                + min(
                    0.75,
                    (
                        rewind - 45.0
                    )
                    / 100.0,
                )
            )

        visual_score = (
            render * 0.30
            + semantic * 0.17
            + composition * 0.14
            + motion * 0.25
            + ending_margin * 0.14
            - repetition_penalty
        )

        score = (
            visual_score
            - chronology_penalty
        )

        scored_endings.append(
            {
                "candidate": candidate,
                "score": float(score),
                "visual_score":
                    float(visual_score),
                "timestamp":
                    float(timestamp),
                "delta":
                    float(ending_delta),
                "rewind":
                    float(rewind),
                "chronology_penalty":
                    float(chronology_penalty),
                "safe":
                    bool(
                        rewind
                        <= ENDING_REWIND_TOLERANCE
                    ),
            }
        )

    if not scored_endings:

        raise RuntimeError(
            "V15.1 ending selector received "
            "no ending candidates."
        )

    ########################################################
    # HARD PREFERENCE:
    # choose among chronology-safe endings whenever one
    # exists.
    ########################################################

    safe_endings = [
        item
        for item in scored_endings
        if item["safe"]
    ]

    if safe_endings:

        best_end_item = max(
            safe_endings,
            key=lambda item:
                item["score"],
        )

        ending_selection_mode = (
            "CHRONOLOGY SAFE"
        )

    else:

        ####################################################
        # If the source pool genuinely contains no safe
        # ending, minimize rewind first and visual score
        # second.
        ####################################################

        best_end_item = max(
            scored_endings,
            key=lambda item: (
                -item["rewind"],
                item["score"],
            ),
        )

        ending_selection_mode = (
            "MINIMUM REWIND FALLBACK"
        )

    best_end = (
        best_end_item[
            "candidate"
        ]
    )

    best_end_score = float(
        best_end_item[
            "score"
        ]
    )

    output[-1] = best_end

    print(
        "ENDING MODE:",
        ending_selection_mode,
    )

    print(
        "ENDING DELTA:",
        round(
            float(
                best_end_item[
                    "delta"
                ]
            ),
            2,
        ),
        "sec",
    )

    print(
        "ENDING REWIND:",
        round(
            float(
                best_end_item[
                    "rewind"
                ]
            ),
            2,
        ),
        "sec",
    )

    print(
        "ENDING CHRONOLOGY PENALTY:",
        round(
            float(
                best_end_item[
                    "chronology_penalty"
                ]
            ),
            4,
        ),
    )
'''

if old not in text:
    raise RuntimeError(
        "Exact V14.1 ending selector was not found. "
        "NO SOURCE CHANGES MADE."
    )

patched = text.replace(
    old,
    new,
    1,
)

if patched.count(MARKER) != 1:
    raise RuntimeError(
        "Unexpected V15.1 marker count."
    )

path.write_text(
    patched,
    encoding="utf-8",
)

try:
    py_compile.compile(
        str(path),
        doraise=True,
    )

except Exception:
    shutil.copy2(
        backup,
        path,
    )

    print()
    print(
        "COMPILE FAILED - BACKUP RESTORED"
    )

    raise

print()
print("========== V15.1 VERIFICATION ==========")

checks = {
    "Ending chronology guard":
        MARKER in patched,

    "5 second tolerance":
        "ENDING_REWIND_TOLERANCE = 5.0"
        in patched,

    "Safe ending pool":
        "safe_endings = ["
        in patched,

    "Chronology safe mode":
        '"CHRONOLOGY SAFE"'
        in patched,

    "Minimum rewind fallback":
        '"MINIMUM REWIND FALLBACK"'
        in patched,

    "Ending delta diagnostic":
        '"ENDING DELTA:"'
        in patched,

    "Ending rewind diagnostic":
        '"ENDING REWIND:"'
        in patched,

    "V14 continuity preserved":
        "def continuity_qa_v14("
        in patched,

    "V15 viewer QA preserved":
        "def final_viewer_qa_v15("
        in patched,
}

failed = []

for name, passed in checks.items():

    print(
        "[PASS]" if passed else "[FAIL]",
        name,
    )

    if not passed:
        failed.append(name)

if failed:

    shutil.copy2(
        backup,
        path,
    )

    raise RuntimeError(
        "V15.1 verification failed: "
        + str(failed)
    )

print()
print("COMPILE: OK")
print()
print(
    "V15.1 ENDING CHRONOLOGY FIX INSTALLED"
)
print(
    "FULL VIDEO RENDER: NOT STARTED"
)
