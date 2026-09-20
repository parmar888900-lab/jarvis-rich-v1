"""Deterministic research confidence scoring."""

import re


class ResearchConfidenceScorer:
    """Score research quality from 0 to 100."""

    MAX_SCORE = 100.0

    STOP_WORDS = {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "for",
        "from",
        "has",
        "have",
        "in",
        "is",
        "it",
        "of",
        "on",
        "or",
        "the",
        "to",
        "was",
        "were",
        "with",
    }

    def score(
        self,
        topic: str,
        sources: list[dict],
    ) -> dict:
        """Return total confidence and component scores."""

        if not sources:
            return {
                "score": 0.0,
                "relevance": 0.0,
                "diversity": 0.0,
                "provider_confidence": 0.0,
                "evidence": 0.0,
            }

        relevance = self._relevance(
            topic,
            sources,
        )

        diversity = self._diversity(
            sources
        )

        provider_confidence = (
            self._provider_confidence(
                sources
            )
        )

        evidence = self._evidence(
            sources
        )

        # Relevance is the confidence gate.
        #
        # Independent publishers and substantial evidence
        # only strengthen confidence when those sources are
        # actually about the researched topic.
        relevance_ratio = min(
            max(
                relevance / 40.0,
                0.0,
            ),
            1.0,
        )

        supporting_score = (
            diversity
            + provider_confidence
            + evidence
        )

        total = (
            relevance
            + (
                supporting_score
                * relevance_ratio
            )
        )

        return {
            "score": round(
                min(
                    max(total, 0.0),
                    self.MAX_SCORE,
                ),
                2,
            ),
            "relevance": relevance,
            "diversity": diversity,
            "provider_confidence": (
                provider_confidence
            ),
            "evidence": evidence,
            "relevance_ratio": round(
                relevance_ratio,
                3,
            ),
        }

    def _relevance(
        self,
        topic: str,
        sources: list[dict],
    ) -> float:
        """
        Measure how strongly result headlines overlap
        with meaningful terms from the research topic.
        """

        topic_terms = self._terms(topic)

        if not topic_terms:
            return 0.0

        similarities = []

        for source in sources:
            title_terms = self._terms(
                str(
                    source.get(
                        "title",
                        "",
                    )
                    or ""
                )
            )

            if not title_terms:
                similarities.append(0.0)
                continue

            overlap = (
                topic_terms
                & title_terms
            )

            similarities.append(
                len(overlap)
                / len(topic_terms)
            )

        average = (
            sum(similarities)
            / len(similarities)
        )

        return round(
            min(
                average * 40.0,
                40.0,
            ),
            2,
        )

    @staticmethod
    def _diversity(
        sources: list[dict],
    ) -> float:
        """
        Reward independent publishers/providers.

        Five results from one publisher should not receive
        the same confidence as five independent publishers.
        """

        identities = set()

        for source in sources:
            identity = str(
                source.get("publisher")
                or source.get("source")
                or ""
            ).strip().lower()

            if identity:
                identities.add(identity)

        if not identities:
            return 0.0

        return round(
            min(
                len(identities) / 4.0,
                1.0,
            )
            * 20.0,
            2,
        )

    @staticmethod
    def _provider_confidence(
        sources: list[dict],
    ) -> float:
        """Average provider-supplied confidence."""

        values = []

        for source in sources:
            try:
                value = float(
                    source.get(
                        "confidence",
                        0.0,
                    )
                    or 0.0
                )
            except (TypeError, ValueError):
                value = 0.0

            values.append(
                min(
                    max(value, 0.0),
                    1.0,
                )
            )

        if not values:
            return 0.0

        average = (
            sum(values)
            / len(values)
        )

        return round(
            average * 20.0,
            2,
        )

    @staticmethod
    def _evidence(
        sources: list[dict],
    ) -> float:
        """
        Reward sources containing usable research text,
        rather than empty search-result shells.
        """

        usable = 0

        for source in sources:
            content = str(
                source.get(
                    "content",
                    "",
                )
                or ""
            ).strip()

            if len(content) >= 40:
                usable += 1

        return round(
            min(
                usable / 4.0,
                1.0,
            )
            * 20.0,
            2,
        )

    def _terms(
        self,
        value: str,
    ) -> set[str]:
        words = re.findall(
            r"[^\W_]+",
            value.lower(),
            flags=re.UNICODE,
        )

        return {
            word
            for word in words
            if (
                len(word) >= 3
                and word
                not in self.STOP_WORDS
            )
        }
