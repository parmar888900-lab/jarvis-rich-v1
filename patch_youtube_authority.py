from pathlib import Path

path = Path(
    r"backend/services/research/providers/youtube.py"
)

text = path.read_text(
    encoding="utf-8"
)

start = text.find(
    "    @classmethod\n"
    "    def _authority_score("
)

end = text.find(
    "    @staticmethod\n"
    "    def _relevance_score(",
    start,
)

if start < 0 or end < 0:
    raise RuntimeError(
        "Authority scoring section not found."
    )

replacement = '''    @classmethod
    def _authority_score(
        cls,
        *,
        title: str,
        channel_title: str,
    ) -> float:

        channel = " ".join(
            str(
                channel_title
            ).lower().split()
        )

        title_lower = (
            str(title).lower()
        )

        score = 35.0

        ####################################################
        # Authority must come primarily from the CHANNEL,
        # not from a brand name appearing in the title.
        ####################################################

        exact_high_authority = {
            "rolex",
            "nasa",
            "boeing",
            "airbus",
            "apple",
            "nvidia",
            "microsoft",
            "ferrari",
            "porsche",
            "marvel entertainment",
            "warner bros. pictures",
            "warner bros. entertainment",
            "universal pictures",
            "paramount pictures",
            "sony pictures entertainment",
            "national geographic",
            "smithsonian channel",
        }

        if channel in exact_high_authority:
            score = 100.0

        elif any(
            term == channel
            for term in cls.OFFICIAL_TERMS
        ):
            score = 95.0

        ####################################################
        # Explicit official-channel naming helps, but does
        # not automatically equal first-party authority.
        ####################################################

        elif (
            "official" in channel
            or channel.endswith(
                " official"
            )
        ):
            score = 80.0

        ####################################################
        # Established specialist channels still have some
        # source value, but remain below first-party media.
        ####################################################

        elif any(
            term in channel
            for term in (
                "watchfinder",
                "crown & caliber",
                "bob's watches",
                "wristcheck",
                "hodinkee",
                "watchbox",
            )
        ):
            score = 65.0

        ####################################################
        # Penalize low-value derivative/reaction content.
        ####################################################

        combined = (
            channel
            + " "
            + title_lower
        )

        if any(
            term in combined
            for term in cls.LOW_VALUE_TERMS
        ):
            score -= 30.0

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

'''

text = (
    text[:start]
    + replacement
    + text[end:]
)

path.write_text(
    text,
    encoding="utf-8",
)

print(
    "SUCCESS: YouTube authority scoring fixed."
)
