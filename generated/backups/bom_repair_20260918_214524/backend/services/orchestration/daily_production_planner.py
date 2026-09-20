"""Daily autonomous production planning for Jarvis Rich V1."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from backend.services.intelligence.genre_topic_selector import (
    GenreTopicSelector,
    TopicCandidate,
)
from backend.services.orchestration.daily_format_rotator import (
    DailyFormatRotator,
)


@dataclass(slots=True)
class DailyProductionItem:
    slot_index: int
    format_name: str
    topic: str
    topic_score: float
    source_hint: str

    def to_dict(self) -> dict:
        return asdict(self)


class DailyProductionPlanner:
    """
    Build one autonomous Rich V1 production batch.

    Guarantees:
        - 3-4+ slots may be requested
        - six-format rotation is preserved
        - no duplicate topic inside one batch
        - topics are reserved immediately
        - rotation cursor persists across days
    """

    def __init__(
        self,
        *,
        state_path: str | Path = (
            "generated/state/"
            "daily_production_state.json"
        ),
        history_path: str | Path = (
            "generated/state/"
            "topic_history.json"
        ),
    ) -> None:

        self.state_path = Path(
            state_path
        )

        self.state_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.rotator = (
            DailyFormatRotator()
        )

        self.selector = (
            GenreTopicSelector(
                history_path=history_path,
            )
        )

    def build_plan(
        self,
        *,
        daily_target: int = 4,
    ) -> list[DailyProductionItem]:

        state = self._load_state()

        cursor = int(
            state.get(
                "format_cursor",
                0,
            )
        )

        slots = self.rotator.build_slots(
            cursor=cursor,
            daily_target=daily_target,
        )

        reserved_topics: set[str] = set()

        plan: list[
            DailyProductionItem
        ] = []

        for slot in slots:

            candidate = (
                self._select_unique(
                    format_name=(
                        slot.format_name
                    ),
                    reserved_topics=(
                        reserved_topics
                    ),
                )
            )

            key = (
                candidate.topic
                .strip()
                .lower()
            )

            reserved_topics.add(
                key
            )

            ################################################
            # Reserve immediately so later slots cannot
            # reuse this topic.
            ################################################

            self.selector.mark_used(
                candidate
            )

            plan.append(
                DailyProductionItem(
                    slot_index=(
                        slot.slot_index
                    ),
                    format_name=(
                        slot.format_name
                    ),
                    topic=(
                        candidate.topic
                    ),
                    topic_score=(
                        candidate.final_score
                    ),
                    source_hint=(
                        candidate.source_hint
                    ),
                )
            )

        next_cursor = (
            self.rotator.next_cursor(
                cursor=cursor,
                produced_count=len(
                    plan
                ),
            )
        )

        self._save_state(
            {
                "format_cursor": (
                    next_cursor
                ),
            }
        )

        return plan

    def _select_unique(
        self,
        *,
        format_name: str,
        reserved_topics: set[str],
    ) -> TopicCandidate:

        pool = (
            self.selector
            ._seed_candidates(
                format_name
            )
        )

        ####################################################
        # Remove topics already selected earlier in this
        # batch before asking normal history selection.
        ####################################################

        pool = [
            candidate
            for candidate in pool
            if (
                candidate.topic
                .strip()
                .lower()
                not in reserved_topics
            )
        ]

        return self.selector.select(
            format_name=format_name,
            candidates=pool,
        )

    def _load_state(
        self,
    ) -> dict:

        if not self.state_path.exists():
            return {
                "format_cursor": 0,
            }

        try:

            data = json.loads(
                self.state_path.read_text(
                    encoding="utf-8"
                )
            )

        except Exception:
            return {
                "format_cursor": 0,
            }

        if not isinstance(
            data,
            dict,
        ):
            return {
                "format_cursor": 0,
            }

        return data

    def _save_state(
        self,
        state: dict,
    ) -> None:

        self.state_path.write_text(
            json.dumps(
                state,
                indent=2,
            ),
            encoding="utf-8",
        )
