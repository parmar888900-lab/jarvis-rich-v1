"""Editorial coverage, continuity, and hook/ending checks for Rich V1."""

from __future__ import annotations

import math

from backend.services.video.clip_matcher import MatchedClip
from backend.services.video.v18_final_master import (
    V18_MAX_MAJOR_BACKWARD_JUMPS,
)


class EditorialSequence:
    """
    Production-safe subset of the V18 editorial contract.

    Fail closed when matched coverage is insufficient. Never invent
    unrelated filler shots to complete a sequence.
    """

    MIN_MATCH_RATIO = 1.0
    MIN_MATCHED_BEATS = 8
    MAJOR_BACKWARD_JUMP = 18.0

    def require_coverage(
        self,
        *,
        beats: list[dict],
        matches: list[MatchedClip],
    ) -> None:

        required_ids = [
            str(
                beat.get(
                    "beat_id",
                    "",
                )
            ).strip()
            for beat in beats
            if str(
                beat.get(
                    "beat_id",
                    "",
                )
            ).strip()
        ]

        if not required_ids:
            raise RuntimeError(
                "No visual beats were produced for matching."
            )

        matched_ids = {
            match.beat_id
            for match in matches
            if match.beat_id
        }

        missing = [
            beat_id
            for beat_id in required_ids
            if beat_id not in matched_ids
        ]

        required_count = max(
            self.MIN_MATCHED_BEATS,
            math.ceil(
                len(required_ids)
                * self.MIN_MATCH_RATIO
            ),
        )

        required_count = min(
            required_count,
            len(required_ids),
        )

        if len(matches) < required_count or missing:

            raise RuntimeError(
                "Insufficient relevant authorized footage. "
                f"Required beats: {len(required_ids)}. "
                f"Matched: {len(matches)}. "
                f"Unmatched: {missing}"
            )

    def require_same_source_continuity(
        self,
        matches: list[MatchedClip],
    ) -> None:

        jumps = []

        for index in range(
            1,
            len(matches),
        ):

            previous = matches[index - 1]
            current = matches[index]

            if (
                previous.source_path
                != current.source_path
            ):
                continue

            delta = (
                current.start_time
                - previous.start_time
            )

            if delta < -self.MAJOR_BACKWARD_JUMP:

                jumps.append(
                    (
                        index,
                        index + 1,
                        round(delta, 2),
                    )
                )

        if len(jumps) > V18_MAX_MAJOR_BACKWARD_JUMPS:

            raise RuntimeError(
                "Editorial continuity failed: major same-source "
                f"backward jumps {jumps}"
            )

    @staticmethod
    def apply_hook_ending_order(
        matches: list[MatchedClip],
    ) -> list[MatchedClip]:
        """Preserve planned beat order; hook is first, payoff last."""

        return list(matches)
