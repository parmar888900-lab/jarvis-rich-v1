from difflib import SequenceMatcher


class TrendDeduplicator:
    """
    Removes duplicate or very similar trends.
    """

    def __init__(self, similarity_threshold: float = 0.75):
        self.similarity_threshold = similarity_threshold

    def _similarity(self, a: str, b: str) -> float:
        return SequenceMatcher(
            None,
            a.lower(),
            b.lower(),
        ).ratio()

    def deduplicate(self, trends: list[dict]) -> list[dict]:
        unique = []

        for trend in trends:
            duplicate = False

            for existing in unique:
                similarity = self._similarity(
                    trend["title"],
                    existing["title"],
                )

                if similarity >= self.similarity_threshold:
                    duplicate = True

                    if trend.get("score", 0) > existing.get("score", 0):
                        existing.update(trend)

                    break

            if not duplicate:
                unique.append(trend)

        return unique