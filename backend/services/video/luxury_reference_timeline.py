"""Measured timeline for the locked Rich V1 luxury benchmark."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LuxuryReferenceShot:
    index: int
    start: float
    end: float

    @property
    def duration(self) -> float:
        return round(
            self.end - self.start,
            3,
        )


class LuxuryReferenceTimeline:
    """
    Timing extracted from benchmark reference 11756.mp4.

    Reference:
        duration ~= 72.968 s
        1080x2400
        60 fps

    These timings reproduce the reference's cut rhythm while allowing
    Jarvis to use new subject-specific footage.
    """

    REFERENCE_NAME = "11756.mp4"

    WIDTH = 1080
    HEIGHT = 2400
    FPS = 60

    CUTS = (
        0.000,
        0.332,
        4.832,
        8.218,
        12.834,
        15.573,
        17.234,
        19.377,
        21.017,
        22.895,
        24.340,
        30.100,
        31.793,
        35.097,
        38.884,
        41.189,
        42.849,
        47.267,
        48.545,
        49.456,
        50.865,
        53.025,
        54.752,
        57.074,
        60.843,
        63.367,
        66.871,
        68.530,
        69.346,
        72.452,
        72.968,
    )

    @classmethod
    def shots(
        cls,
    ) -> list[LuxuryReferenceShot]:

        return [
            LuxuryReferenceShot(
                index=index,
                start=start,
                end=end,
            )
            for index, (
                start,
                end,
            ) in enumerate(
                zip(
                    cls.CUTS,
                    cls.CUTS[1:],
                ),
                start=1,
            )
        ]
