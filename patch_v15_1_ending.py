from pathlib import Path
import py_compile
import sys

path = Path("render_narrative_movie_proof_v15.py")
text = path.read_text(encoding="utf-8")

marker = "V15_1_ENDING_CHRONOLOGY_GUARD"

if marker in text:
    print("V15.1 ending chronology guard already installed.")
    py_compile.compile(str(path), doraise=True)
    print("COMPILE: OK")
    sys.exit(0)

old = '''    best_hook = best_item["candidate"]'''

if old not in text:
    raise RuntimeError(
        "Could not locate best_hook assignment. "
        "No source changes made."
    )

# We deliberately patch immediately before best_hook.
# At this point hook selection is complete and the function
# continues into ending selection.
text = text.replace(
    old,
    '''    # V15_1_ENDING_CHRONOLOGY_GUARD
    best_hook = best_item["candidate"]''',
    1,
)

# Locate ending assignment later in the same function.
start = text.index("V15_1_ENDING_CHRONOLOGY_GUARD")
function_end = text.find(
    "\\ndef ",
    start,
)

if function_end == -1:
    function_end = len(text)

section = text[start:function_end]

possible_assignments = (
    'best_ending = max(',
    'best_end = max(',
    'ending = max(',
)

found = None

for candidate in possible_assignments:
    if candidate in section:
        found = candidate
        break

if found is None:
    # Print ending-related lines so we can patch the exact
    # implementation without guessing.
    print()
    print("ENDING ASSIGNMENT NOT AUTOMATICALLY RECOGNIZED.")
    print("Relevant lines:")
    print()

    lines = section.splitlines()

    for number, line in enumerate(lines, 1):
        if (
            "ending" in line.lower()
            or "end_" in line.lower()
        ):
            print(f"{number:04d}: {line}")

    raise RuntimeError(
        "Ending selector shape differs from expected forms. "
        "Marker was added only; restoring source."
    )

# Restore original before applying the real patch because
# the marker above was only used for discovery.
text = text.replace(
    '''    # V15_1_ENDING_CHRONOLOGY_GUARD
    best_hook = best_item["candidate"]''',
    old,
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

print("ENDING SELECTOR FOUND:", found)
print("DISCOVERY COMPILE: OK")
print()
print(
    "Selector located safely. "
    "Run the PowerShell audit printed below before rendering."
)
