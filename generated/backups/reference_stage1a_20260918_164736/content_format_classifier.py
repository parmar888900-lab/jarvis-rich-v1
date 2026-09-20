"""Reference-style content format classification for Jarvis Rich V1."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class ContentFormatDecision:
    format_name: str
    target_duration_min: float
    target_duration_max: float
    preferred_media: list[str]
    narration_mode: str
    pacing: str
    reason: str
    rights_gate_required: bool = False


class ContentFormatClassifier:
    """Choose the correct production format for a topic."""

    MOVIE_COMMENTARY_GENRES = {
        "famous_movie_commentary",
        "movie_facts",
        "scene_breakdowns",
        "movies_filmmaking",
    }

    EXPLAINER_GENRES = {
        "science_engineering",
        "technology",
        "machines_manufacturing",
        "space_aviation",
        "interesting_products",
        "luxury_money",
    }

    STORY_GENRES = {
        "business_stories",
        "history_inventions",
        "human_performance",
    }

    def classify(
        self,
        *,
        topic: str,
        genre: str,
        authorized_movie_source: bool = False,
    ) -> ContentFormatDecision:

        genre = str(genre).strip().lower()

        if genre == "famous_movie_commentary":
            return ContentFormatDecision(
                format_name="famous_movie_commentary",
                target_duration_min=35.0,
                target_duration_max=60.0,
                preferred_media=[
                    "authorized_movie_excerpt",
                    "licensed_promotional_media",
                    "licensed_image",
                    "archive_media",
                ],
                narration_mode="original_commentary_voiceover",
                pacing="cinematic_information_density",
                reason=(
                    "Famous-movie topic requires original commentary "
                    "with supporting authorized visual material."
                ),
                rights_gate_required=True,
            )

        if genre in {
            "movie_facts",
            "scene_breakdowns",
            "movies_filmmaking",
        }:
            return ContentFormatDecision(
                format_name="cinematic_explainer",
                target_duration_min=35.0,
                target_duration_max=60.0,
                preferred_media=[
                    "authorized_movie_excerpt",
                    "licensed_promotional_media",
                    "licensed_image",
                    "archive_media",
                ],
                narration_mode="voiceover",
                pacing="cinematic",
                reason=(
                    "Film-related explanation requires cinematic "
                    "visual planning and original narration."
                ),
                rights_gate_required=True,
            )

        if genre in self.EXPLAINER_GENRES:
            return ContentFormatDecision(
                format_name="visual_explainer",
                target_duration_min=35.0,
                target_duration_max=65.0,
                preferred_media=[
                    "licensed_video",
                    "licensed_image",
                    "diagram",
                    "archive_media",
                ],
                narration_mode="voiceover",
                pacing="information_density",
                reason="Reference-style visual explainer.",
            )

        if genre in self.STORY_GENRES:
            return ContentFormatDecision(
                format_name="documentary_story",
                target_duration_min=40.0,
                target_duration_max=75.0,
                preferred_media=[
                    "licensed_video",
                    "archive_media",
                    "licensed_image",
                    "documents",
                ],
                narration_mode="voiceover",
                pacing="story_progression",
                reason="Reference-style documentary story.",
            )

        return ContentFormatDecision(
            format_name="visual_explainer",
            target_duration_min=35.0,
            target_duration_max=60.0,
            preferred_media=[
                "licensed_video",
                "licensed_image",
            ],
            narration_mode="voiceover",
            pacing="information_density",
            reason="Default Rich V1 reference format.",
        )
