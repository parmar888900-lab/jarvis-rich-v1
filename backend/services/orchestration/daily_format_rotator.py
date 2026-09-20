"""Daily format rotation for Jarvis Rich V1."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ProductionSlot:
    slot_index: int
    format_name: str


class DailyFormatRotator:
    """
    Rotate Rich V1 production across the six locked benchmark formats.

    Default target:
        4 videos per day

    The cursor advances continuously so the system does not reset to
    the same format every morning.
    """

    FORMATS = (
        "movie_facts",
        "cinematic_movie_edit",
        "curiosity_story",
        "luxury_product",
        "science_explainer",
        "business_wealth",
    )

    DEFAULT_DAILY_TARGET = 4

    def build_slots(
        self,
        *,
        cursor: int = 0,
        daily_target: int | None = None,
    ) -> list[ProductionSlot]:

        target = (
            daily_target
            if daily_target is not None
            else self.DEFAULT_DAILY_TARGET
        )

        if target < 1:
            raise ValueError(
                "daily_target must be at least 1."
            )

        slots: list[ProductionSlot] = []

        for offset in range(target):

            format_name = self.FORMATS[
                (cursor + offset)
                % len(self.FORMATS)
            ]

            slots.append(
                ProductionSlot(
                    slot_index=offset + 1,
                    format_name=format_name,
                )
            )

        return slots

    def next_cursor(
        self,
        *,
        cursor: int,
        produced_count: int,
    ) -> int:

        return (
            cursor + produced_count
        ) % len(self.FORMATS)
