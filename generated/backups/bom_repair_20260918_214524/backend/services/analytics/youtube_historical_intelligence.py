"""Historical YouTube performance intelligence."""

from __future__ import annotations

import re
from typing import Any


class YoutubeHistoricalIntelligence:
    """
    Convert historical YouTube performance into bounded
    evidence for future topic selection.

    A score of 50 is neutral. Historical evidence cannot
    influence production until the performance analyzer
    marks the channel strategy-ready.
    """

    NEUTRAL_SCORE = 50.0
    MAX_ADJUSTMENT = 8.0

    MIN_TOKEN_LENGTH = 3
    MIN_SIMILARITY = 0.15

    STOP_WORDS = frozenset(
        {
            "the",
            "and",
            "for",
            "that",
            "this",
            "with",
            "from",
            "into",
            "when",
            "what",
            "why",
            "how",
            "you",
            "your",
            "was",
            "were",
            "are",
            "but",
            "not",
            "too",
            "who",
            "his",
            "her",
            "their",
            "they",
            "them",
            "then",
            "until",
            "after",
            "before",
            "would",
            "could",
            "should",
            "happened",
            "believe",
        }
    )

    @classmethod
    def _tokens(
        cls,
        text: str,
    ) -> set[str]:
        """Return normalized informative title tokens."""

        words = re.findall(
            r"[a-z0-9]+",
            str(text or "").lower(),
        )

        return {
            word
            for word in words
            if (
                len(word)
                >= cls.MIN_TOKEN_LENGTH
                and word
                not in cls.STOP_WORDS
            )
        }

    @classmethod
    def _title_similarity(
        cls,
        left: str,
        right: str,
    ) -> float:
        """
        Return Jaccard similarity for informative title tokens.
        """

        left_tokens = cls._tokens(left)
        right_tokens = cls._tokens(right)

        if (
            not left_tokens
            or not right_tokens
        ):
            return 0.0

        intersection = (
            left_tokens
            & right_tokens
        )

        union = (
            left_tokens
            | right_tokens
        )

        if not union:
            return 0.0

        return (
            len(intersection)
            / float(len(union))
        )

    @staticmethod
    def _category(
        item: dict[str, Any],
    ) -> str:
        """Extract normalized category when available."""

        knowledge = item.get(
            "knowledge"
        )

        if isinstance(
            knowledge,
            dict,
        ):
            value = knowledge.get(
                "category"
            )

            if value:
                return str(
                    value
                ).strip().lower()

        return str(
            item.get(
                "category",
                "",
            )
            or ""
        ).strip().lower()

    def evaluate(
        self,
        candidate: dict[str, Any],
        performance: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """
        Evaluate historical evidence for one future candidate.

        Historical influence is fail-closed:
        no strategy readiness -> neutral score and zero adjustment.
        """

        if not isinstance(
            performance,
            dict,
        ):
            return self._neutral(
                "performance_evidence_unavailable"
            )

        confidence = self._bounded(
            performance.get(
                "confidence",
                0.0,
            ),
            minimum=0.0,
            maximum=1.0,
        )

        if (
            performance.get(
                "strategy_ready"
            )
            is not True
        ):
            return self._neutral(
                "performance_evidence_not_ready",
                confidence=confidence,
            )

        historical = performance.get(
            "videos"
        )

        if not isinstance(
            historical,
            list,
        ) or not historical:
            return self._neutral(
                "no_historical_videos",
                confidence=confidence,
            )

        candidate_title = str(
            candidate.get(
                "title",
                "",
            )
            or ""
        ).strip()

        candidate_category = (
            self._category(
                candidate
            )
        )

        matches: list[
            dict[str, Any]
        ] = []

        for video in historical:
            if not isinstance(
                video,
                dict,
            ):
                continue

            similarity = (
                self._title_similarity(
                    candidate_title,
                    str(
                        video.get(
                            "title",
                            "",
                        )
                        or ""
                    ),
                )
            )

            historical_category = (
                self._category(
                    video
                )
            )

            category_match = (
                bool(candidate_category)
                and bool(
                    historical_category
                )
                and candidate_category
                == historical_category
            )

            # Category is useful supporting evidence,
            # but never fabricate it when historical
            # records do not contain one.
            match_strength = similarity

            if category_match:
                match_strength = max(
                    match_strength,
                    0.35,
                )

            if (
                match_strength
                < self.MIN_SIMILARITY
            ):
                continue

            performance_score = (
                self._bounded(
                    video.get(
                        "performance_score",
                        self.NEUTRAL_SCORE,
                    ),
                    minimum=0.0,
                    maximum=100.0,
                )
            )

            matches.append(
                {
                    "video_id": str(
                        video.get(
                            "video_id",
                            "",
                        )
                        or ""
                    ),
                    "title": str(
                        video.get(
                            "title",
                            "",
                        )
                        or ""
                    ),
                    "similarity": round(
                        similarity,
                        4,
                    ),
                    "category_match": (
                        category_match
                    ),
                    "match_strength": round(
                        match_strength,
                        4,
                    ),
                    "performance_score": round(
                        performance_score,
                        2,
                    ),
                }
            )

        if not matches:
            return self._neutral(
                "no_relevant_historical_matches",
                confidence=confidence,
            )

        weight_total = sum(
            float(
                match[
                    "match_strength"
                ]
            )
            for match in matches
        )

        if weight_total <= 0:
            return self._neutral(
                "no_weighted_historical_evidence",
                confidence=confidence,
            )

        historical_score = (
            sum(
                float(
                    match[
                        "performance_score"
                    ]
                )
                * float(
                    match[
                        "match_strength"
                    ]
                )
                for match in matches
            )
            / weight_total
        )

        historical_score = (
            self._bounded(
                historical_score,
                minimum=0.0,
                maximum=100.0,
            )
        )

        # Convert 0-100 historical performance around
        # neutral 50 into -1..+1.
        direction = (
            historical_score
            - self.NEUTRAL_SCORE
        ) / self.NEUTRAL_SCORE

        direction = self._bounded(
            direction,
            minimum=-1.0,
            maximum=1.0,
        )

        adjustment = (
            direction
            * self.MAX_ADJUSTMENT
            * confidence
        )

        adjustment = self._bounded(
            adjustment,
            minimum=-self.MAX_ADJUSTMENT,
            maximum=self.MAX_ADJUSTMENT,
        )

        matches.sort(
            key=lambda match: (
                match[
                    "match_strength"
                ],
                match[
                    "performance_score"
                ],
            ),
            reverse=True,
        )

        return {
            "strategy_ready": True,
            "historical_score": round(
                historical_score,
                2,
            ),
            "confidence": round(
                confidence,
                4,
            ),
            "adjustment": round(
                adjustment,
                2,
            ),
            "match_count": len(
                matches
            ),
            "matches": matches,
            "reason": (
                "historical_evidence_applied"
            ),
        }

    def _neutral(
        self,
        reason: str,
        *,
        confidence: float = 0.0,
    ) -> dict[str, Any]:
        """Return stable neutral historical evidence."""

        return {
            "strategy_ready": False,
            "historical_score": (
                self.NEUTRAL_SCORE
            ),
            "confidence": round(
                confidence,
                4,
            ),
            "adjustment": 0.0,
            "match_count": 0,
            "matches": [],
            "reason": reason,
        }

    @staticmethod
    def _bounded(
        value: Any,
        *,
        minimum: float,
        maximum: float,
    ) -> float:
        """Safely parse and clamp a numeric value."""

        try:
            number = float(
                value
            )
        except (
            TypeError,
            ValueError,
        ):
            number = minimum

        return min(
            max(
                number,
                minimum,
            ),
            maximum,
        )
