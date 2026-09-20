"""Production-safe V18 visual helpers.

Extracted from the benchmark's proven focus, motion, and vertical
dynamic-crop behavior without copying the 12k-line proof script.
"""

from __future__ import annotations

import cv2
import numpy as np


def detect_faces(frame):
    """Best-effort face detection. Optional if Haar is unavailable."""

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

    except Exception:
        return []


def focus_x(frame):

    faces = detect_faces(
        frame
    )

    h, w = frame.shape[:2]

    if faces:

        centers = [
            x + fw / 2
            for x, y, fw, fh
            in faces
        ]

        return float(
            np.mean(
                centers
            )
            / w
        )

    gray = cv2.cvtColor(
        frame,
        cv2.COLOR_RGB2GRAY,
    )

    edges = cv2.Sobel(
        gray,
        cv2.CV_32F,
        1,
        0,
        ksize=3,
    )

    energy = np.abs(
        edges
    ).sum(
        axis=0
    )

    if energy.sum() <= 0:
        return 0.5

    xs = np.arange(
        w,
        dtype=np.float32,
    )

    center = float(
        (
            xs * energy
        ).sum()
        / energy.sum()
    )

    return max(
        0.15,
        min(
            0.85,
            center / w,
        ),
    )


def composition_score(
    frame,
) -> tuple[float, float]:

    focus = focus_x(
        frame
    )

    faces = detect_faces(
        frame
    )

    score = 0.72

    if faces:

        h, w = frame.shape[:2]

        centers = []
        total_area = 0.0

        for x, y, fw, fh in faces:

            centers.append(
                (
                    x + fw / 2
                )
                / w
            )

            total_area += (
                fw * fh
            ) / (
                w * h
            )

        group_center = float(
            np.mean(
                centers
            )
        )

        focus = group_center

        if 0.16 <= group_center <= 0.84:
            score += 0.14

        if 0.01 <= total_area <= 0.35:
            score += 0.12

    else:

        if 0.20 <= focus <= 0.80:
            score += 0.08

    return (
        min(
            score,
            1.0,
        ),
        max(
            0.12,
            min(
                0.88,
                float(focus),
            ),
        ),
    )


def motion_score(
    source,
    timestamp: float,
    window: float = 0.22,
) -> float:

    if source.duration is None or source.duration <= 0.02:
        return 0.0

    left = max(
        0.0,
        timestamp - window,
    )

    right = min(
        source.duration - 0.01,
        timestamp + window,
    )

    if right <= left:
        return 0.0

    frame_a = source.get_frame(
        left
    ).astype(
        np.uint8
    )

    frame_b = source.get_frame(
        right
    ).astype(
        np.uint8
    )

    gray_a = cv2.cvtColor(
        frame_a,
        cv2.COLOR_RGB2GRAY,
    )

    gray_b = cv2.cvtColor(
        frame_b,
        cv2.COLOR_RGB2GRAY,
    )

    difference = cv2.absdiff(
        gray_a,
        gray_b,
    )

    raw = float(
        difference.mean()
    )

    return min(
        raw / 35.0,
        1.0,
    )


def build_focus_track(
    source,
    *,
    start: float,
    end: float,
):

    if end <= start:

        return [
            (
                0.0,
                0.5,
            )
        ]

    times = np.linspace(
        start,
        end,
        15,
    )

    raw = []

    for timestamp in times:

        frame = source.get_frame(
            float(timestamp)
        ).astype(
            np.uint8
        )

        _, focus = composition_score(
            frame
        )

        raw.append(
            max(
                0.12,
                min(
                    0.88,
                    float(focus),
                ),
            )
        )

    median_values = []

    for index in range(
        len(raw)
    ):

        left = max(
            0,
            index - 2,
        )

        right = min(
            len(raw),
            index + 3,
        )

        median_values.append(
            float(
                np.median(
                    raw[
                        left:right
                    ]
                )
            )
        )

    alpha = 0.36

    smooth = [
        median_values[0]
    ]

    for value in median_values[1:]:

        previous = smooth[-1]

        smooth.append(
            previous
            + alpha
            * (
                value
                - previous
            )
        )

    stable = [
        smooth[0]
    ]

    dead_zone = 0.025
    max_step = 0.042

    for target in smooth[1:]:

        current = stable[-1]
        delta = target - current

        if abs(delta) <= dead_zone:
            stable.append(current)
            continue

        delta = max(
            -max_step,
            min(
                max_step,
                delta,
            ),
        )

        stable.append(
            max(
                0.12,
                min(
                    0.88,
                    current + delta,
                ),
            )
        )

    return [
        (
            float(timestamp - start),
            float(focus),
        )
        for timestamp, focus
        in zip(
            times,
            stable,
        )
    ]


def dynamic_crop(
    clip,
    focus_track,
    *,
    width: int,
    height: int,
):

    track_t = np.array(
        [
            item[0]
            for item
            in focus_track
        ],
        dtype=np.float32,
    )

    track_x = np.array(
        [
            item[1]
            for item
            in focus_track
        ],
        dtype=np.float32,
    )

    def transform(
        get_frame,
        t,
    ):

        frame = np.asarray(
            get_frame(t)
        ).astype(
            np.uint8
        )

        h, w = frame.shape[:2]

        scale = max(
            width / w,
            height / h,
        )

        rw = int(
            np.ceil(
                w * scale
            )
        )

        rh = int(
            np.ceil(
                h * scale
            )
        )

        resized = cv2.resize(
            frame,
            (
                rw,
                rh,
            ),
            interpolation=(
                cv2.INTER_LANCZOS4
            ),
        )

        focus = float(
            np.interp(
                float(t),
                track_t,
                track_x,
            )
        )

        cx = rw * focus
        half = width / 2

        cx = max(
            half,
            min(
                rw - half,
                cx,
            ),
        )

        x1 = int(
            round(
                cx - half
            )
        )

        x1 = max(
            0,
            min(
                rw - width,
                x1,
            ),
        )

        y1 = max(
            0,
            int(
                (
                    rh - height
                )
                / 2
            ),
        )

        output = resized[
            y1:y1 + height,
            x1:x1 + width,
        ]

        if (
            output.shape[0] != height
            or output.shape[1] != width
        ):

            output = cv2.resize(
                output,
                (
                    width,
                    height,
                ),
                interpolation=(
                    cv2.INTER_LANCZOS4
                ),
            )

        return output

    return clip.transform(
        transform
    )
