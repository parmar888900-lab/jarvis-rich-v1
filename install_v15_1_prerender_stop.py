from pathlib import Path
import py_compile

path = Path("render_narrative_movie_proof_v15.py")
text = path.read_text(encoding="utf-8")

marker = "V15_1_PRERENDER_TEST_STOP"

if marker not in text:

    old = '''    voice = build_voice(
        config,
        narration=V13_NARRATION,
    )

    clips = []'''

    new = '''    # V15_1_PRERENDER_TEST_STOP
    print()
    print("======================================================")
    print(" V15.1 PRE-RENDER TEST COMPLETE")
    print(" VIDEO ENCODING SKIPPED")
    print("======================================================")
    return

    voice = build_voice(
        config,
        narration=V13_NARRATION,
    )

    clips = []'''

    if old not in text:
        raise RuntimeError(
            "Could not locate voice/render boundary. "
            "No changes made."
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

py_compile.compile(
    str(path),
    doraise=True,
)

print("PRE-RENDER STOP: INSTALLED")
print("COMPILE: OK")
