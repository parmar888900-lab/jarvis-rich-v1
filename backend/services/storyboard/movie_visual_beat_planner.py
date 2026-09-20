"""Movie visual-beat planning for Jarvis Rich V1."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass

from backend.models.generated_content import GeneratedContent


@dataclass(slots=True)
class MovieVisualBeat:
    """
    One visual editing beat inside a movie-commentary Short.
    """

    beat_id: str
    narration_index: int
    purpose: str
    visual_query: str
    preferred_media: list[str]
    target_duration: float
    priority: str
    evidence_ids: list[str]

    def to_dict(self) -> dict:
        return asdict(self)


class MovieVisualBeatPlanner:
    """
    Convert four narration lines into a fast multi-cut movie
    commentary visual plan.

    This planner describes required visuals.
    It does not authorize or download copyrighted footage.
    """

    TARGET_BEATS = 14
    MIN_BEATS = 10
    MAX_BEATS = 16

    BEATS_PER_LINE = (
        4,
        4,
        3,
        3,
    )

    STOPWORDS = {
        "about",
        "after",
        "again",
        "against",
        "also",
        "because",
        "being",
        "between",
        "both",
        "could",
        "does",
        "from",
        "have",
        "into",
        "more",
        "most",
        "movie",
        "scene",
        "scenes",
        "that",
        "their",
        "there",
        "these",
        "they",
        "this",
        "those",
        "through",
        "very",
        "what",
        "when",
        "where",
        "which",
        "while",
        "with",
        "would",
    }

    def plan(
        self,
        *,
        content: GeneratedContent,
        movie_title: str,
        topic: str,
    ) -> list[MovieVisualBeat]:

        lines = list(
            content.script_lines
        )

        if len(lines) != 4:
            raise RuntimeError(
                "Movie visual planning requires "
                "exactly four narration lines."
            )

        raw_evidence = (
            content.metadata.get(
                "evidence_ids",
                [],
            )
        )

        if not isinstance(
            raw_evidence,
            list,
        ):
            raw_evidence = []

        beats: list[MovieVisualBeat] = []

        for narration_index, line in enumerate(
            lines,
            start=1,
        ):

            target_count = self.BEATS_PER_LINE[
                narration_index - 1
            ]

            concepts = self._visual_concepts(
                line=line,
                movie_title=movie_title,
                topic=topic,
                target_count=target_count,
            )

            evidence_ids = []

            if (
                narration_index - 1
                < len(raw_evidence)
                and isinstance(
                    raw_evidence[
                        narration_index - 1
                    ],
                    list,
                )
            ):
                evidence_ids = [
                    str(item).strip().upper()
                    for item in raw_evidence[
                        narration_index - 1
                    ]
                    if str(item).strip()
                ]

            for local_index, query in enumerate(
                concepts,
                start=1,
            ):

                beats.append(
                    MovieVisualBeat(
                        beat_id=(
                            f"n{narration_index}"
                            f"_b{local_index}"
                        ),
                        narration_index=narration_index,
                        purpose=self._purpose(
                            narration_index,
                            local_index,
                        ),
                        visual_query=query,
                        preferred_media=(
                            self._preferred_media(
                                narration_index,
                                local_index,
                            )
                        ),
                        target_duration=(
                            self._target_duration(
                                narration_index,
                                local_index,
                            )
                        ),
                        priority=(
                            "high"
                            if (
                                narration_index == 1
                                or narration_index == 4
                            )
                            else "normal"
                        ),
                        evidence_ids=evidence_ids,
                    )
                )

        if not (
            self.MIN_BEATS
            <= len(beats)
            <= self.MAX_BEATS
        ):
            raise RuntimeError(
                "Movie beat count outside allowed "
                f"range: {len(beats)}"
            )

        return beats

    def _visual_concepts(
        self,
        *,
        line: str,
        movie_title: str,
        topic: str,
        target_count: int,
    ) -> list[str]:

        text = " ".join(
            str(line).split()
        )

        lower = text.lower()

        candidates: list[str] = []

        ####################################################
        # Movie-specific concrete concepts
        ####################################################

        concept_rules = [
            (
                "mirror dimension",
                f"{movie_title} Mirror Dimension",
            ),
            (
                "visual effects",
                f"{movie_title} visual effects",
            ),
            (
                "vfx",
                f"{movie_title} VFX production",
            ),
            (
                "scott derrickson",
                "Scott Derrickson Doctor Strange director",
            ),
            (
                "different dimensions",
                f"{movie_title} different dimensions",
            ),
            (
                "dimensions",
                f"{movie_title} dimensional action",
            ),
            (
                "action sequence",
                f"{movie_title} action sequence",
            ),
            (
                "action sequences",
                f"{movie_title} action sequences",
            ),
            (
                "superhero action",
                f"{movie_title} superhero action",
            ),
            (
                "mysticism",
                f"{movie_title} mystic arts visuals",
            ),
            (
                "surreal",
                f"{movie_title} surreal visual effects",
            ),
            (
                "inception",
                f"{movie_title} Mirror Dimension Inception comparison",
            ),
            (
                "production",
                f"{movie_title} behind the scenes production",
            ),
            (
                "effects",
                f"{movie_title} visual effects breakdown",
            ),
        ]

        for trigger, query in concept_rules:

            if trigger in lower:
                candidates.append(
                    query
                )

        ####################################################
        # Concrete entities
        ####################################################

        if "derrickson" in lower:
            candidates.append(
                "Scott Derrickson directing Doctor Strange"
            )

        if "framestore" in lower:
            candidates.append(
                "Framestore Doctor Strange visual effects"
            )

        if (
            "industrial light" in lower
            or "ilm" in lower
        ):
            candidates.append(
                "Industrial Light Magic Doctor Strange VFX"
            )

        ####################################################
        # Topic-level visual anchors
        ####################################################

        topic_lower = topic.lower()

        if "mirror dimension" in topic_lower:
            candidates.extend(
                [
                    f"{movie_title} Mirror Dimension",
                    f"{movie_title} Mirror Dimension chase",
                    f"{movie_title} dimensional city visuals",
                ]
            )

        ####################################################
        # Safe generic production anchors
        ####################################################

        candidates.extend(
            [
                f"{movie_title} film still",
                f"{movie_title} visual effects",
                f"{movie_title} production still",
                f"{movie_title} action sequence",
                f"{movie_title} behind the scenes",
            ]
        )

        ####################################################
        # Deduplicate and reject weak fragments
        ####################################################

        result = []
        seen = set()

        for candidate in candidates:

            clean = " ".join(
                str(candidate).split()
            ).strip()

            key = clean.lower()

            if not clean:
                continue

            if key in seen:
                continue

            if len(clean.split()) < 2:
                continue

            if clean.endswith("'s"):
                continue

            seen.add(key)

            result.append(
                clean
            )

            if len(result) >= target_count:
                break

        if len(result) < target_count:
            raise RuntimeError(
                "Movie visual planner could not create "
                "enough concrete visual concepts for: "
                f"{line}"
            )

        return result


    @staticmethod
    def _purpose(
        narration_index: int,
        local_index: int,
    ) -> str:

        if narration_index == 1:
            return (
                "hook_subject"
                if local_index == 1
                else "hook_detail"
            )

        if narration_index == 2:
            return (
                "filmmaker_context"
                if local_index == 1
                else "explanation"
            )

        if narration_index == 3:
            return (
                "technical_detail"
                if local_index == 1
                else "supporting_visual"
            )

        return (
            "payoff"
            if local_index == 1
            else "closing_visual"
        )

    @staticmethod
    def _preferred_media(
        narration_index: int,
        local_index: int,
    ) -> list[str]:

        if narration_index == 2:
            return [
                "authorized_movie_excerpt",
                "licensed_production_media",
                "licensed_image",
            ]

        if narration_index == 3:
            return [
                "licensed_production_media",
                "authorized_movie_excerpt",
                "licensed_image",
            ]

        return [
            "authorized_movie_excerpt",
            "licensed_promotional_media",
            "licensed_image",
        ]

    @staticmethod
    def _target_duration(
        narration_index: int,
        local_index: int,
    ) -> float:

        if (
            narration_index == 1
            and local_index == 1
        ):
            return 2.2

        if narration_index == 4:
            return 3.0

        return 2.6

    @staticmethod
    def to_dicts(
        beats: list[MovieVisualBeat],
    ) -> list[dict]:

        return [
            beat.to_dict()
            for beat in beats
        ]
