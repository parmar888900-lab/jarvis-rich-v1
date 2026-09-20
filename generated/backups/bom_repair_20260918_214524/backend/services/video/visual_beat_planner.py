"""Visual beat planning for reference-quality Rich V1 Shorts."""

from __future__ import annotations

import re

from dataclasses import dataclass, asdict

from backend.models.generated_content import GeneratedContent
from backend.services.video.media_query_builder import (
    MediaQueryBuilder,
)


@dataclass(slots=True)
class VisualBeat:
    beat_id: str
    narration_index: int
    purpose: str
    search_query: str
    preferred_media: list[str]
    target_duration: float
    emphasis: str


class VisualBeatPlanner:
    """Convert narration sections into distinct visual beats."""

    MIN_BEATS = 8
    MAX_BEATS = 14

    def __init__(self) -> None:
        self.query_builder = MediaQueryBuilder()

    def plan(
        self,
        *,
        content: GeneratedContent,
        topic: str,
        genre: str,
        format_name: str,
    ) -> list[VisualBeat]:

        lines = list(
            content.script_lines
        )

        if not lines:
            raise RuntimeError(
                "Cannot build visual beats from empty script."
            )

        beats: list[VisualBeat] = []
        used_queries: set[str] = set()

        for narration_index, line in enumerate(
            lines,
            start=1,
        ):

            queries = self._queries_for_line(
                topic=topic,
                genre=genre,
                line=line,
            )

            per_line = (
                3
                if narration_index <= 2
                else 2
            )

            selected_queries = []

            for query in queries:

                key = query.lower().strip()

                if (
                    not key
                    or key in used_queries
                ):
                    continue

                used_queries.add(key)
                selected_queries.append(
                    query
                )

                if len(
                    selected_queries
                ) >= per_line:
                    break

            for local_index, query in enumerate(
                selected_queries,
                start=1,
            ):

                beats.append(
                    VisualBeat(
                        beat_id=(
                            f"n{narration_index}"
                            f"_b{local_index}"
                        ),
                        narration_index=narration_index,
                        purpose=self._purpose(
                            narration_index=narration_index,
                            local_index=local_index,
                        ),
                        search_query=query,
                        preferred_media=(
                            self._preferred_media(
                                format_name
                            )
                        ),
                        target_duration=(
                            self._target_duration(
                                format_name
                            )
                        ),
                        emphasis=(
                            "high"
                            if narration_index == 1
                            else "normal"
                        ),
                    )
                )

        beats = beats[
            :self.MAX_BEATS
        ]

        if len(beats) < self.MIN_BEATS:
            beats = self._pad_beats(
                beats=beats,
                topic=topic,
                genre=genre,
                format_name=format_name,
                used_queries=used_queries,
            )

        return beats

    def _queries_for_line(
        self,
        *,
        topic: str,
        genre: str,
        line: str,
    ) -> list[str]:

        queries = (
            self.query_builder.build(
                topic=topic,
                genre=genre,
                narration=line,
            )
        )

        ####################################################
        # Add narration-specific concrete noun phrases.
        ####################################################

        words = re.findall(
            r"[A-Za-z0-9]+",
            line.lower(),
        )

        stopwords = {
            "this",
            "that",
            "with",
            "from",
            "their",
            "they",
            "have",
            "more",
            "into",
            "because",
            "about",
            "which",
            "while",
            "were",
            "used",
            "using",
            "designed",
            "helps",
            "help",
            "proper",
            "ensure",
            "extremely",
        }

        useful = [
            word
            for word in words
            if (
                len(word) >= 4
                and word not in stopwords
            )
        ]

        phrase_candidates = []

        if len(useful) >= 2:
            phrase_candidates.append(
                " ".join(
                    useful[:2]
                )
            )

        if len(useful) >= 3:
            phrase_candidates.append(
                " ".join(
                    useful[:3]
                )
            )

        if len(useful) >= 4:
            phrase_candidates.append(
                " ".join(
                    useful[-3:]
                )
            )

        output = []

        ####################################################
        # Prefer concrete alias/media queries over full topic.
        ####################################################

        for query in [
            *queries,
            *phrase_candidates,
        ]:

            clean = " ".join(
                str(query).split()
            ).strip()

            if not clean:
                continue

            if clean.lower() == topic.lower():
                continue

            if clean not in output:
                output.append(clean)

        return output

    @staticmethod
    def to_dicts(
        beats: list[VisualBeat],
    ) -> list[dict]:

        return [
            asdict(beat)
            for beat in beats
        ]

    @staticmethod
    def _purpose(
        *,
        narration_index: int,
        local_index: int,
    ) -> str:

        if narration_index == 1:
            return (
                "hook_subject"
                if local_index == 1
                else "hook_detail"
            )

        if narration_index in {
            2,
            3,
        }:
            return (
                "explanation"
                if local_index == 1
                else "supporting_detail"
            )

        return (
            "payoff"
            if local_index == 1
            else "closing_visual"
        )

    @staticmethod
    def _preferred_media(
        format_name: str,
    ) -> list[str]:

        if format_name == "movie_clip":
            return [
                "authorized_movie_video",
            ]

        if format_name == "documentary_story":
            return [
                "licensed_video",
                "archive_media",
                "licensed_image",
            ]

        return [
            "licensed_video",
            "licensed_image",
            "diagram",
        ]

    @staticmethod
    def _target_duration(
        format_name: str,
    ) -> float:

        if format_name == "movie_clip":
            return 3.5

        if format_name == "documentary_story":
            return 3.0

        return 2.5

    def _pad_beats(
        self,
        *,
        beats: list[VisualBeat],
        topic: str,
        genre: str,
        format_name: str,
        used_queries: set[str],
    ) -> list[VisualBeat]:

        result = list(beats)

        fallback_queries = (
            self.query_builder.build(
                topic=topic,
                genre=genre,
                narration=topic,
            )
        )

        for query in fallback_queries:

            if len(result) >= self.MIN_BEATS:
                break

            clean = query.strip()

            if (
                not clean
                or clean.lower()
                in used_queries
                or clean.lower()
                == topic.lower()
            ):
                continue

            used_queries.add(
                clean.lower()
            )

            result.append(
                VisualBeat(
                    beat_id=(
                        f"extra_b"
                        f"{len(result)+1}"
                    ),
                    narration_index=(
                        (len(result) % 4) + 1
                    ),
                    purpose="supporting_detail",
                    search_query=clean,
                    preferred_media=(
                        self._preferred_media(
                            format_name
                        )
                    ),
                    target_duration=(
                        self._target_duration(
                            format_name
                        )
                    ),
                    emphasis="normal",
                )
            )

        return result
