"""Evergreen content selection for Jarvis Rich V1.

Replaces trend-first topic selection while preserving the existing
production orchestration contract.
"""

from __future__ import annotations

from collections import deque
import json
from pathlib import Path
from typing import Any


class EvergreenContentSelector:
    """Select high-curiosity evergreen short-form topics."""

    GENRES = {
        "famous_movie_commentary": [
            "Why Doctor Strange's mirror dimension scenes work so well",
            "How Avengers Endgame builds tension before the final battle",
            "Why Interstellar's docking scene feels so intense",
            "How The Dark Knight makes the Joker feel unpredictable",
            "Why Spider-Man No Way Home's portal scene was so effective",
            "How Inception makes complicated ideas visually understandable",
            "Why Iron Man's first suit-building scene became iconic",
            "How Jurassic Park made its dinosaurs feel believable",
            "Why The Matrix bullet-time sequence changed action movies",
            "How Pirates of the Caribbean introduced Jack Sparrow",
        ],
        "movie_facts": [
            "How filmmakers created Doctor Strange's reality-bending visuals",
            "Why practical effects still matter in modern blockbusters",
            "How movie sound designers create sounds that do not exist",
            "Why blockbuster movies use previsualization before filming",
            "How actors perform scenes surrounded by green screens",
        ],
        "scene_breakdowns": [
            "Why great movie openings reveal character without explaining everything",
            "How filmmakers use camera movement to increase tension",
            "Why silence can make a movie scene more intense",
            "How editing changes the emotional impact of a scene",
            "Why certain movie reveals feel satisfying",
        ],
        "business_stories": [
            "Why Costco keeps its hot dog price unusually low",
            "How LEGO survived one of the worst periods in its history",
            "Why IKEA designs products around flat-pack shipping",
            "How Nintendo survived long before video games",
            "Why some companies deliberately sell products at a loss",
        ],
        "luxury_money": [
            "What actually makes a luxury mechanical watch expensive",
            "Why private jets cost so much to operate",
            "How supercar manufacturers justify extreme prices",
            "Why some hotel suites cost thousands per night",
            "What makes handmade luxury products so expensive",
        ],
        "science_engineering": [
            "Why airplane windows are rounded instead of square",
            "How suspension bridges handle enormous loads",
            "Why skyscrapers are designed to move in strong winds",
            "How aircraft black boxes survive extreme crashes",
            "Why train wheels are shaped differently from car wheels",
        ],
        "human_performance": [
            "How elite runners train their bodies for endurance",
            "Why professional cyclists train at high altitude",
            "How reaction-time training works for elite athletes",
            "Why marathon pacing matters more than starting speed",
            "How athletes recover between intense competitions",
        ],
        "technology": [
            "How modern phone cameras stabilize moving video",
            "Why data centers use enormous cooling systems",
            "How noise-cancelling headphones cancel sound",
            "Why modern processors contain billions of transistors",
            "How GPS determines where you are",
        ],
        "movies_filmmaking": [
            "How filmmakers create realistic miniature worlds",
            "Why movie sound effects are often recorded separately",
            "How practical effects can make scenes look more realistic",
            "Why filmmakers use green screens",
            "How animated movies simulate realistic lighting",
        ],
        "history_inventions": [
            "Why shipping containers changed world trade",
            "How the barcode transformed modern stores",
            "Why the invention of the elevator changed cities",
            "How refrigeration changed the way humans eat",
            "Why standardized time zones became necessary",
        ],
        "machines_manufacturing": [
            "How CNC machines cut metal with extreme precision",
            "Why industrial robots dominate modern car factories",
            "How glass bottles are manufactured at high speed",
            "How factories produce thousands of cans every hour",
            "Why precision bearings matter inside machines",
        ],
        "space_aviation": [
            "Why rockets launch vertically",
            "How spacecraft survive the heat of reentry",
            "Why commercial airplanes cruise so high",
            "How satellites stay in orbit without falling straight down",
            "Why aircraft wings bend during flight",
        ],
        "interesting_products": [
            "Why pencils are usually hexagonal",
            "How vacuum-insulated bottles keep drinks hot or cold",
            "Why running shoes use different types of foam",
            "How mechanical keyboards register a key press",
            "Why safety glass breaks differently from ordinary glass",
        ],
    }

    WEIGHTS = {
        "curiosity": 0.25,
        "story_strength": 0.20,
        "visual_supply": 0.20,
        "evergreen_value": 0.15,
        "credibility": 0.10,
        "channel_fit": 0.10,
    }

    STATE_PATH = Path("data/evergreen_selector_state.json")

    FORMAT_GENRES = {
        "movie_facts": (
            "famous_movie_commentary",
            "movie_facts",
            "scene_breakdowns",
            "movies_filmmaking",
        ),
        "cinematic_movie_edit": (
            "famous_movie_commentary",
            "scene_breakdowns",
            "movies_filmmaking",
        ),
        "curiosity_story": (
            "history_inventions",
            "technology",
            "interesting_products",
            "human_performance",
        ),
        "luxury_product": (
            "luxury_money",
            "interesting_products",
        ),
        "science_explainer": (
            "science_engineering",
            "machines_manufacturing",
            "space_aviation",
            "technology",
        ),
        "business_wealth": (
            "business_stories",
            "luxury_money",
        ),
    }

    def __init__(self) -> None:
        self._recent: deque[str] = deque(maxlen=40)
        self._cursor = 0
        self._format_cursor = 0
        self._load_state()

    def _load_state(self) -> None:
        try:
            if not self.STATE_PATH.exists():
                return

            data = json.loads(
                self.STATE_PATH.read_text(encoding="utf-8")
            )

            recent = data.get("recent_topics", [])
            if isinstance(recent, list):
                self._recent.extend(
                    str(item)
                    for item in recent[-40:]
                    if item
                )

            self._cursor = int(data.get("cursor", 0))
            self._format_cursor = int(
                data.get("format_cursor", 0)
            )

        except Exception:
            # State corruption must never stop production.
            self._recent.clear()
            self._cursor = 0
            self._format_cursor = 0

    def _save_state(self) -> None:
        self.STATE_PATH.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        payload = {
            "recent_topics": list(self._recent),
            "cursor": self._cursor,
            "format_cursor": self._format_cursor,
        }

        temp_path = self.STATE_PATH.with_suffix(".tmp")

        temp_path.write_text(
            json.dumps(payload, indent=2),
            encoding="utf-8",
        )

        temp_path.replace(self.STATE_PATH)

    def select(
        self,
        *,
        content_id: str,
        performance: dict[str, Any] | None = None,
        goal_strategy: dict[str, Any] | None = None,
        format_name: str | None = None,
    ) -> dict[str, Any] | None:
        """Return one production-authorized evergreen candidate."""

        candidates: list[dict[str, Any]] = []

        allowed_genres = (
            self.FORMAT_GENRES.get(format_name)
            if format_name
            else None
        )

        for genre, topics in self.GENRES.items():
            if (
                allowed_genres is not None
                and genre not in allowed_genres
            ):
                continue

            for topic in topics:
                if topic in self._recent:
                    continue

                candidates.append(
                    self._build_candidate(
                        title=topic,
                        genre=genre,
                        content_id=content_id,
                    )
                )

        if not candidates:
            self._recent.clear()

            return self.select(
                content_id=content_id,
                performance=performance,
                goal_strategy=goal_strategy,
                format_name=format_name,
            )

        candidates.sort(
            key=lambda item: (
                item["production_selection"][
                    "production_score"
                ],
                item["title"],
            ),
            reverse=True,
        )

        # Rotate across equally strong candidates instead of repeatedly
        # choosing the same alphabetically-highest topic.
        index = self._cursor % len(candidates)
        winner = candidates[index]
        self._cursor += 1

        self._recent.append(
            winner["title"]
        )

        winner["production_selection"][
            "selected"
        ] = True

        if format_name:
            winner["locked_format"] = format_name

        self._save_state()

        return winner

    def _build_candidate(
        self,
        *,
        title: str,
        genre: str,
        content_id: str,
    ) -> dict[str, Any]:

        scores = self._score(
            title=title,
            genre=genre,
        )

        production_score = sum(
            scores[name] * weight
            for name, weight in self.WEIGHTS.items()
        )

        return {
            "title": title,
            "topic": title,
            "genre": genre,
            "content_id": content_id,
            "content_strategy": "evergreen_storytelling",
            "requires_trend": False,
            "production_selection": {
                "eligible": True,
                "selected": False,
                "production_score": round(
                    production_score,
                    2,
                ),
                "curiosity_score": scores[
                    "curiosity"
                ],
                "story_strength": scores[
                    "story_strength"
                ],
                "visual_supply": scores[
                    "visual_supply"
                ],
                "evergreen_value": scores[
                    "evergreen_value"
                ],
                "credibility": scores[
                    "credibility"
                ],
                "channel_fit": scores[
                    "channel_fit"
                ],
                "reason": (
                    "Evergreen topic passed Rich V1 "
                    "story and production criteria."
                ),
                "rejection_reasons": [],
            },
        }

    @staticmethod
    def _score(
        *,
        title: str,
        genre: str,
    ) -> dict[str, float]:
        """
        Conservative initial heuristic.

        These scores will later be replaced/adjusted by actual
        channel-performance evidence after the new content engine
        has accumulated enough videos.
        """

        curiosity = 84.0
        story_strength = 82.0
        visual_supply = 86.0
        evergreen_value = 92.0
        credibility = 90.0
        channel_fit = 86.0

        if title.lower().startswith(
            ("why ", "how ", "what ")
        ):
            curiosity += 4.0

        if genre in {
            "science_engineering",
            "machines_manufacturing",
            "space_aviation",
        }:
            visual_supply += 3.0
            evergreen_value += 2.0

        return {
            "curiosity": min(curiosity, 100.0),
            "story_strength": min(
                story_strength,
                100.0,
            ),
            "visual_supply": min(
                visual_supply,
                100.0,
            ),
            "evergreen_value": min(
                evergreen_value,
                100.0,
            ),
            "credibility": min(
                credibility,
                100.0,
            ),
            "channel_fit": min(
                channel_fit,
                100.0,
            ),
        }

