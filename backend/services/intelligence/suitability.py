"""Topic suitability scoring for short-form faceless content."""

import re


class TopicSuitabilityScorer:
    """
    Estimate how suitable a trend is for Jarvis-generated
    short-form faceless content.

    This score is intentionally separate from virality.
    """

    MAX_SCORE = 100.0

    EXPLAINABLE_CATEGORIES = {
        "News",
        "General",
        "technology",
        "todayilearned",
    }

    LOW_CONTEXT_PATTERNS = (
        r"\bofficial\s+(?:video|music video)\b",
        r"\bmusic\s+video\b",
        r"\blyric(?:s)?\b",
        r"\bsong\b",
        r"\btrailer\b",
        r"\bteaser\b",
        r"\blive\s+gameplay\b",
        r"\bgameplay\b",
    )

    CURIOSITY_PATTERNS = (
        r"\bwhy\b",
        r"\bhow\b",
        r"\bwhat\b",
        r"\bfirst\b",
        r"\bnew\b",
        r"\bafter\b",
        r"\bdiscover(?:ed|y)?\b",
        r"\bscientists?\b",
        r"\bresearchers?\b",
        r"\bwarning\b",
        r"\bplans?\b",
    )

    SENSITIVE_PATTERNS = (
        r"\brape\b",
        r"\bsexual\s+assault\b",
        r"\bsuicide\b",
        r"\bself[- ]harm\b",
        r"\bmurder\b",
        r"\bkills?\b",
        r"\bdead\b",
        r"\bdeath\b",
    )

    def score(
        self,
        trend: dict,
    ) -> dict:
        """
        Return suitability score and component breakdown.
        """

        title = str(
            trend.get("title", "") or ""
        ).strip()

        knowledge = (
            trend.get("knowledge")
            or {}
        )

        category = str(
            knowledge.get("category")
            or trend.get("category")
            or ""
        )

        researchability = self._researchability(
            knowledge
        )

        explainability = self._explainability(
            title,
            category,
            knowledge,
        )

        curiosity = self._curiosity(
            title
        )

        transformation = self._transformation_potential(
            title,
            knowledge,
        )

        low_context_penalty = self._low_context_penalty(
            title
        )

        sensitivity_penalty = self._sensitivity_penalty(
            title,
            knowledge,
        )

        research_confidence_penalty = (
            self._research_confidence_penalty(
                knowledge
            )
        )

        total = (
            researchability
            + explainability
            + curiosity
            + transformation
            - low_context_penalty
            - sensitivity_penalty
            - research_confidence_penalty
        )

        total = round(
            min(
                max(total, 0.0),
                self.MAX_SCORE,
            ),
            2,
        )

        return {
            "score": total,
            "researchability": researchability,
            "explainability": explainability,
            "curiosity": curiosity,
            "transformation": transformation,
            "low_context_penalty": low_context_penalty,
            "sensitivity_penalty": sensitivity_penalty,
            "research_confidence_penalty": (
                research_confidence_penalty
            ),
        }

    @staticmethod
    def _researchability(
        knowledge: dict,
    ) -> float:
        """
        Reward topics backed by relevant, corroborated
        research rather than raw result quantity.
        """

        facts = knowledge.get("facts") or []
        sources = knowledge.get("sources") or []

        try:
            confidence = float(
                knowledge.get(
                    "score",
                    0.0,
                )
                or 0.0
            )
        except (TypeError, ValueError):
            confidence = 0.0

        confidence = min(
            max(confidence, 0.0),
            100.0,
        )

        # Research confidence is the primary signal:
        # 0-100 confidence -> 0-20 suitability points.
        confidence_score = (
            confidence / 100.0
        ) * 20.0

        # Evidence quantity contributes only a small
        # supporting bonus. It cannot rescue irrelevant
        # research by itself.
        evidence_bonus = 0.0

        if facts:
            evidence_bonus += min(
                len(facts),
                3,
            ) * 1.0

        if sources:
            evidence_bonus += min(
                len(sources),
                2,
            ) * 1.0

        return round(
            min(
                confidence_score
                + evidence_bonus,
                25.0,
            ),
            2,
        )

    def _explainability(
        self,
        title: str,
        category: str,
        knowledge: dict,
    ) -> float:
        """
        Estimate whether the topic can be explained as
        a standalone narrated short.

        Research-dependent points are gated by research
        confidence so irrelevant search results cannot
        create artificial explainability.
        """

        confidence_ratio = self._confidence_ratio(
            knowledge
        )

        # Intrinsic explainability.
        score = 5.0

        if len(title.split()) >= 5:
            score += 5.0

        # Research-dependent explainability.
        evidence_score = 0.0

        if category in self.EXPLAINABLE_CATEGORIES:
            evidence_score += 5.0

        if knowledge.get("summary"):
            evidence_score += 5.0

        if len(
            knowledge.get("facts") or []
        ) >= 3:
            evidence_score += 5.0

        score += (
            evidence_score
            * confidence_ratio
        )

        return round(
            min(score, 25.0),
            2,
        )

    def _curiosity(
        self,
        title: str,
    ) -> float:
        """Estimate natural curiosity potential."""

        text = title.lower()

        matches = sum(
            1
            for pattern in self.CURIOSITY_PATTERNS
            if re.search(pattern, text)
        )

        score = 5.0 + min(
            matches * 4.0,
            12.0,
        )

        if "?" in title:
            score += 3.0

        return min(score, 20.0)

    def _transformation_potential(
        self,
        title: str,
        knowledge: dict,
    ) -> float:
        """
        Estimate whether available information can support
        an original narrated short.

        Evidence-dependent points are gated by research
        confidence.
        """

        confidence_ratio = self._confidence_ratio(
            knowledge
        )

        facts = knowledge.get("facts") or []
        sources = knowledge.get("sources") or []

        # Intrinsic transformation potential.
        score = 5.0

        if len(title.split()) >= 6:
            score += 5.0

        # Research-dependent transformation potential.
        evidence_score = 0.0

        if len(facts) >= 2:
            evidence_score += 5.0

        if len(sources) >= 2:
            evidence_score += 5.0

        if knowledge.get("summary"):
            evidence_score += 5.0

        score += (
            evidence_score
            * confidence_ratio
        )

        return round(
            min(score, 25.0),
            2,
        )

    @staticmethod
    def _confidence_ratio(
        knowledge: dict,
    ) -> float:
        """
        Convert 0-100 research confidence into a bounded
        0-1 multiplier.
        """

        try:
            confidence = float(
                knowledge.get(
                    "score",
                    0.0,
                )
                or 0.0
            )
        except (TypeError, ValueError):
            confidence = 0.0

        return min(
            max(
                confidence / 100.0,
                0.0,
            ),
            1.0,
        )

    @staticmethod
    def _research_confidence_penalty(
        knowledge: dict,
    ) -> float:
        """
        Penalize topics whose research confidence is too
        weak for reliable automated content production.

        Confidence of 50 or higher receives no penalty.
        Lower confidence scales gradually to a maximum
        penalty of 20 points.
        """

        try:
            confidence = float(
                knowledge.get(
                    "score",
                    0.0,
                )
                or 0.0
            )
        except (TypeError, ValueError):
            confidence = 0.0

        confidence = min(
            max(confidence, 0.0),
            100.0,
        )

        threshold = 50.0

        if confidence >= threshold:
            return 0.0

        deficit_ratio = (
            threshold - confidence
        ) / threshold

        return round(
            min(
                deficit_ratio * 20.0,
                20.0,
            ),
            2,
        )

    def _low_context_penalty(
        self,
        title: str,
    ) -> float:
        """
        Penalize trends whose value depends heavily on
        consuming the original media or knowing a fandom.
        """

        text = title.lower()

        matches = sum(
            1
            for pattern in self.LOW_CONTEXT_PATTERNS
            if re.search(pattern, text)
        )

        return min(
            matches * 8.0,
            25.0,
        )

    def _sensitivity_penalty(
        self,
        title: str,
        knowledge: dict,
    ) -> float:
        """
        Apply a conservative penalty to sensitive topics.

        This is a suitability signal, not the final
        content-safety gate.
        """

        text = " ".join(
            [
                title,
                str(
                    knowledge.get(
                        "summary",
                        "",
                    )
                    or ""
                ),
            ]
        ).lower()

        matches = sum(
            1
            for pattern in self.SENSITIVE_PATTERNS
            if re.search(pattern, text)
        )

        return min(
            matches * 10.0,
            30.0,
        )
