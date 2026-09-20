"""Visual-source planning for Jarvis Rich V1."""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict

from backend.services.llm_service import LLMService


@dataclass(slots=True)
class SourceVisualBeat:
    beat_id: str
    purpose: str
    visual_goal: str
    search_queries: list[str]
    negative_visuals: list[str]

    def to_dict(self) -> dict:
        return asdict(self)


class VisualBeatSourcePlanner:
    """
    Convert a topic + Rich V1 format into exact visual requirements.

    Unlike the old media resolver, this planner does not search one
    broad topic repeatedly. It produces specific visual beats first.
    """

    FORMAT_RULES = {
        "movie_facts": (
            "Use recognizable movie-specific moments, production "
            "footage, VFX breakdown material, actor/director context, "
            "and exact scene-relevant visuals."
        ),
        "cinematic_movie_edit": (
            "Use visually strong character, action, emotional, wide, "
            "detail, and payoff shots from the same movie/source."
        ),
        "curiosity_story": (
            "Use real subject/location/event footage. Avoid generic "
            "stock people or unrelated cinematic filler."
        ),
        "luxury_product": (
            "Use the actual product/model where possible: dial, case, "
            "movement, materials, craftsmanship, wrist/product shots."
        ),
        "science_explainer": (
            "Use real mechanism-specific visuals: exterior, internal "
            "parts, process stages, operation, demonstration, diagrams."
        ),
        "business_wealth": (
            "Use real company/founder/product/factory/headquarters/"
            "historical footage matching the exact claim."
        ),
    }

    def __init__(
        self,
        *,
        llm: LLMService | None = None,
    ) -> None:

        self.llm = (
            llm
            if llm is not None
            else LLMService()
        )

    async def plan(
        self,
        *,
        topic: str,
        format_name: str,
        beat_count: int = 8,
    ) -> list[SourceVisualBeat]:

        clean_topic = " ".join(
            str(topic).split()
        ).strip()

        if not clean_topic:
            raise ValueError(
                "Visual beat planning requires a topic."
            )

        rule = self.FORMAT_RULES.get(
            format_name,
            (
                "Use specific real visuals that directly represent "
                "the topic. Avoid generic filler."
            ),
        )

        prompt = f"""
You are the visual-source planner for a high-retention vertical Short.

TOPIC:
{clean_topic}

FORMAT:
{format_name}

FORMAT VISUAL RULE:
{rule}

Create exactly {beat_count} distinct visual beats.

Each beat must be visually concrete and searchable.

For every beat return:
- beat_id
- purpose
- visual_goal
- search_queries: 3 highly specific search queries
- negative_visuals: 3 descriptions of footage that may look vaguely
  related but must be rejected

Important:
- Do not use generic phrases like "cinematic footage".
- Search queries should identify the actual object, mechanism, person,
  product, location, scene, or process needed.
- Beats should progress logically through the topic.
- For science, show actual mechanism stages.
- For luxury, show the actual product/details.
- For movies, show movie-specific or production-specific footage.
- Avoid generic stock replacements.

Return JSON only:

{{
  "beats": [
    {{
      "beat_id": "b1",
      "purpose": "hook",
      "visual_goal": "...",
      "search_queries": ["...", "...", "..."],
      "negative_visuals": ["...", "...", "..."]
    }}
  ]
}}
"""

        raw = await self.llm.chat(
            [
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            json_mode=True,
        )

        try:

            data = json.loads(
                raw
            )

        except json.JSONDecodeError as exc:

            raise RuntimeError(
                "VisualBeatSourcePlanner returned invalid JSON."
            ) from exc

        rows = data.get(
            "beats",
            []
        )

        if not isinstance(
            rows,
            list,
        ):
            raise RuntimeError(
                "Visual beat planner produced invalid beat list."
            )

        beats: list[
            SourceVisualBeat
        ] = []

        for index, row in enumerate(
            rows,
            start=1,
        ):

            if not isinstance(
                row,
                dict,
            ):
                continue

            goal = " ".join(
                str(
                    row.get(
                        "visual_goal",
                        "",
                    )
                ).split()
            ).strip()

            if not goal:
                continue

            queries = [
                " ".join(
                    str(item).split()
                ).strip()
                for item in row.get(
                    "search_queries",
                    [],
                )
                if str(item).strip()
            ]

            negatives = [
                " ".join(
                    str(item).split()
                ).strip()
                for item in row.get(
                    "negative_visuals",
                    [],
                )
                if str(item).strip()
            ]

            if not queries:
                queries = [
                    goal
                ]

            beats.append(
                SourceVisualBeat(
                    beat_id=str(
                        row.get(
                            "beat_id",
                            f"b{index}",
                        )
                    ),
                    purpose=str(
                        row.get(
                            "purpose",
                            "supporting_visual",
                        )
                    ),
                    visual_goal=goal,
                    search_queries=(
                        queries[:3]
                    ),
                    negative_visuals=(
                        negatives[:3]
                    ),
                )
            )

        if len(beats) < 4:
            raise RuntimeError(
                "Visual beat planner produced too few valid beats."
            )

        return beats[:beat_count]
