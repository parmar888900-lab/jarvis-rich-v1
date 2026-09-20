"""Genre-specific topic selection for Jarvis Rich V1."""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path


@dataclass(slots=True)
class TopicCandidate:
    topic: str
    format_name: str

    popularity_score: float = 0.0
    visual_score: float = 0.0
    freshness_score: float = 0.0
    novelty_score: float = 0.0
    suitability_score: float = 0.0

    source_hint: str = ""

    @property
    def final_score(self) -> float:

        score = (
            self.popularity_score * 0.25
            + self.visual_score * 0.25
            + self.freshness_score * 0.15
            + self.novelty_score * 0.15
            + self.suitability_score * 0.20
        )

        return round(
            max(
                0.0,
                min(
                    score,
                    100.0,
                ),
            ),
            2,
        )

    def to_dict(self) -> dict:
        data = asdict(self)
        data["final_score"] = self.final_score
        return data


class GenreTopicSelector:
    """
    Select production-ready topics for one Rich V1 format.

    This class handles:
        - format-specific seed topics
        - repeat prevention
        - scoring
        - production history

    Live discovery sources will be added on top of this layer.
    """

    FORMAT_SEEDS = {

        "movie_facts": [
            "Avengers Endgame",
            "Interstellar",
            "The Dark Knight",
            "Spider-Man No Way Home",
            "Doctor Strange",
            "Iron Man",
            "Inception",
            "The Batman",
        ],

        "cinematic_movie_edit": [
            "Avengers Endgame",
            "The Dark Knight",
            "Interstellar",
            "Dune",
            "Doctor Strange",
            "Oppenheimer",
            "The Batman",
            "Top Gun Maverick",
        ],

        "curiosity_story": [
            "the world's most dangerous road",
            "the deepest place humans have explored",
            "the strangest abandoned city",
            "the most extreme survival story",
            "the world's most isolated building",
            "a machine that should not work but does",
            "the coldest inhabited place on Earth",
            "the most dangerous airport landing",
        ],

        "luxury_product": [
            "Patek Philippe Grand Complications",
            "Rolex Daytona",
            "Bugatti Tourbillon",
            "Rolls-Royce Droptail",
            "Richard Mille RM 27",
            "Ferrari Daytona SP3",
            "Audemars Piguet Royal Oak",
            "Koenigsegg Jesko",
        ],

        "science_explainer": [
            "how jet engines work",
            "how magnetic levitation works",
            "how suspension bridges stay up",
            "how nuclear fusion works",
            "how a Formula 1 gearbox works",
            "how spacecraft re-enter the atmosphere",
            "how hydraulic systems multiply force",
            "how active aerodynamics works",
        ],

        "business_wealth": [
            "how Nvidia became one of the world's most valuable companies",
            "how Rolex controls scarcity",
            "how Ferrari protects its brand",
            "how Costco makes money",
            "how luxury brands create demand",
            "how Apple built its ecosystem",
            "how LVMH became a luxury empire",
            "how Porsche turned scarcity into profit",
        ],
    }

    def __init__(
        self,
        *,
        history_path: str | Path = (
            "generated/state/topic_history.json"
        ),
    ) -> None:

        self.history_path = Path(
            history_path
        )

        self.history_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

    def select(
        self,
        *,
        format_name: str,
        candidates: list[TopicCandidate] | None = None,
    ) -> TopicCandidate:

        pool = (
            candidates
            if candidates is not None
            else self._seed_candidates(
                format_name
            )
        )

        if not pool:
            raise RuntimeError(
                f"No topic candidates available for {format_name}."
            )

        history = self._load_history()

        used = {
            str(item.get("topic", ""))
            .strip()
            .lower()
            for item in history
        }

        eligible = [
            candidate
            for candidate in pool
            if (
                candidate.topic
                .strip()
                .lower()
                not in used
            )
        ]

        if not eligible:
            raise RuntimeError(
                f"All topic candidates for {format_name} "
                "have already been used."
            )

        ranked = sorted(
            eligible,
            key=lambda item: (
                item.final_score,
                item.visual_score,
                item.suitability_score,
            ),
            reverse=True,
        )

        winner = ranked[0]

        return winner

    def mark_used(
        self,
        candidate: TopicCandidate,
    ) -> None:

        history = self._load_history()

        history.append(
            candidate.to_dict()
        )

        self.history_path.write_text(
            json.dumps(
                history,
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    def recent_topics(
        self,
        *,
        limit: int = 50,
    ) -> list[dict]:

        history = self._load_history()

        return history[
            -max(
                0,
                int(limit),
            ):
        ]

    def _seed_candidates(
        self,
        format_name: str,
    ) -> list[TopicCandidate]:

        topics = self.FORMAT_SEEDS.get(
            format_name,
            [],
        )

        candidates = []

        for index, topic in enumerate(
            topics
        ):

            # Deterministic baseline scores for architecture tests.
            # Live discovery will replace these with actual signals.
            candidates.append(
                TopicCandidate(
                    topic=topic,
                    format_name=format_name,
                    popularity_score=(
                        82.0
                        - index * 2.0
                    ),
                    visual_score=(
                        90.0
                        - index
                    ),
                    freshness_score=70.0,
                    novelty_score=78.0,
                    suitability_score=88.0,
                    source_hint="seed",
                )
            )

        return candidates

    def _load_history(
        self,
    ) -> list[dict]:

        if not self.history_path.exists():
            return []

        try:

            data = json.loads(
                self.history_path.read_text(
                    encoding="utf-8"
                )
            )

        except Exception:
            return []

        if not isinstance(
            data,
            list,
        ):
            return []

        return [
            item
            for item in data
            if isinstance(
                item,
                dict,
            )
        ]
