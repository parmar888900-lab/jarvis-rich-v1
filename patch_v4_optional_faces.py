from pathlib import Path

path = Path(
    "render_narrative_movie_proof_v4.py"
)

text = path.read_text(
    encoding="utf-8"
)

start = text.find(
    "def detect_faces(frame):"
)

end = text.find(
    "\ndef focus_x(frame):",
    start,
)

if start < 0 or end < 0:
    raise RuntimeError(
        "detect_faces function block not found."
    )

replacement = '''def detect_faces(frame):
    """
    Best-effort face detection.

    Some OpenCV builds do not expose the legacy Haar
    CascadeClassifier API. Face detection is therefore
    optional: focus_x() will fall back to visual-detail
    centering when it is unavailable.
    """

    if not hasattr(
        cv2,
        "CascadeClassifier",
    ):
        return []

    if not hasattr(
        cv2,
        "data",
    ):
        return []

    try:

        cascade_path = (
            cv2.data.haarcascades
            + "haarcascade_frontalface_default.xml"
        )

        cascade = cv2.CascadeClassifier(
            cascade_path
        )

        if (
            hasattr(
                cascade,
                "empty",
            )
            and cascade.empty()
        ):
            return []

        gray = cv2.cvtColor(
            frame,
            cv2.COLOR_RGB2GRAY,
        )

        faces = cascade.detectMultiScale(
            gray,
            scaleFactor=1.08,
            minNeighbors=5,
            minSize=(35, 35),
        )

        return list(
            faces
        )

    except Exception as exc:

        print(
            "FACE DETECTION FALLBACK:",
            type(exc).__name__,
        )

        return []


'''

text = (
    text[:start]
    + replacement
    + text[end + 1:]
)

path.write_text(
    text,
    encoding="utf-8",
)

print(
    "SUCCESS: face detection made optional."
)
