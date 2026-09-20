"""Contextual licensed-media queries for movie commentary."""

from __future__ import annotations

import re


class MovieContextualQueryBuilder:
    """
    Convert movie-specific visual requests into broader factual,
    contextually relevant searches suitable for licensed B-roll.

    These queries never claim that contextual material is footage
    from the movie itself.
    """

    MAX_QUERIES = 8

    RULES = (
        (
            (
                "mirror dimension",
                "dimension",
                "dimensional",
            ),
            (
                "surreal city architecture",
                "geometric city perspective",
                "abstract dimensional geometry",
                "distorted urban architecture",
                "impossible geometry architecture",
            ),
        ),
        (
            (
                "visual effects",
                "vfx",
                "effects",
            ),
            (
                "visual effects production",
                "film compositing workstation",
                "computer generated imagery production",
                "digital effects studio",
                "motion graphics production",
            ),
        ),
        (
            (
                "director",
                "derrickson",
                "directing",
            ),
            (
                "film director on set",
                "movie director behind camera",
                "film production set",
                "director filmmaking",
            ),
        ),
        (
            (
                "mystic",
                "mysticism",
                "magic",
            ),
            (
                "abstract mystical geometry",
                "mandala geometric pattern",
                "sacred geometry artwork",
                "abstract glowing geometry",
            ),
        ),
        (
            (
                "action",
                "superhero",
                "chase",
            ),
            (
                "cinematic action filmmaking",
                "film action sequence production",
                "movie stunt production",
                "cinematic city action",
            ),
        ),
        (
            (
                "production",
                "behind the scenes",
                "filmmaking",
            ),
            (
                "film production behind the scenes",
                "movie camera production",
                "cinema production crew",
                "film set camera crew",
            ),
        ),
        (
            (
                "city",
                "urban",
            ),
            (
                "dramatic city architecture",
                "urban architecture perspective",
                "city skyline perspective",
            ),
        ),
    )

    @classmethod
    def build(
        cls,
        *,
        visual_query: str,
        purpose: str = "",
    ) -> list[str]:

        text = (
            f"{visual_query} {purpose}"
            .lower()
        )

        queries: list[str] = []

        for triggers, fallbacks in cls.RULES:

            if any(
                trigger in text
                for trigger in triggers
            ):
                queries.extend(
                    fallbacks
                )

        ####################################################
        # Purpose-aware fallbacks
        ####################################################

        if purpose == "filmmaker_context":
            queries.extend(
                [
                    "film director on set",
                    "filmmaking camera crew",
                    "movie production set",
                ]
            )

        elif purpose == "technical_detail":
            queries.extend(
                [
                    "visual effects workstation",
                    "digital compositing film",
                    "computer graphics production",
                ]
            )

        elif purpose == "supporting_visual":
            queries.extend(
                [
                    "cinematic abstract geometry",
                    "surreal architecture",
                    "film visual effects production",
                ]
            )

        elif purpose in {
            "hook_subject",
            "hook_detail",
        }:
            queries.extend(
                [
                    "surreal cinematic architecture",
                    "dramatic geometric city",
                ]
            )

        elif purpose in {
            "payoff",
            "closing_visual",
        }:
            queries.extend(
                [
                    "cinematic city perspective",
                    "abstract film visual effects",
                ]
            )

        ####################################################
        # Normalize + deduplicate
        ####################################################

        output: list[str] = []
        seen: set[str] = set()

        for query in queries:

            clean = re.sub(
                r"\s+",
                " ",
                str(query),
            ).strip()

            key = clean.lower()

            if (
                not clean
                or key in seen
            ):
                continue

            seen.add(key)
            output.append(clean)

            if len(output) >= cls.MAX_QUERIES:
                break

        return output
