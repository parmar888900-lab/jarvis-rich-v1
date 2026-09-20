"""Reference-style content format classification for Jarvis Rich V1."""

from __future__ import annotations

from dataclasses import dataclass

from backend.services.intelligence.reference_format_profiles import (
    get_reference_profile,
)


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
    reference_profile: dict | None = None


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

        del topic
        del authorized_movie_source

        genre = str(genre).strip().lower()

        # ----------------------------------------------------
        # Resolve Jarvis's six reference-format identities.
        # ----------------------------------------------------

        profile = get_reference_profile(genre)

        profile_dict = (
            profile.to_dict()
            if profile is not None
            else None
        )

        # ----------------------------------------------------
        # Famous movie commentary
        #
        # Keep the existing format_name because ContentGenerator
        # has specialized evidence validation for this path.
        # The reference profile still maps its viewing mechanics
        # to movie_facts.
        # ----------------------------------------------------

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
                narration_mode=(
                    "original_commentary_voiceover"
                ),
                pacing=(
                    profile.pacing_strategy
                    if profile is not None
                    else "cinematic_information_density"
                ),
                reason=(
                    "Grounded famous-movie commentary using the "
                    "movie-facts reference retention profile."
                ),
                rights_gate_required=True,
                reference_profile=profile_dict,
            )

        # ----------------------------------------------------
        # Movie facts / scene breakdowns / filmmaking
        # ----------------------------------------------------

        if genre in {
            "movie_facts",
            "scene_breakdowns",
            "movies_filmmaking",
        }:

            return ContentFormatDecision(
                format_name="cinematic_explainer",
                target_duration_min=(
                    profile.target_duration_min
                    if profile is not None
                    else 35.0
                ),
                target_duration_max=(
                    profile.target_duration_max
                    if profile is not None
                    else 60.0
                ),
                preferred_media=(
                    list(profile.preferred_media)
                    if profile is not None
                    else [
                        "authorized_movie_excerpt",
                        "licensed_promotional_media",
                        "licensed_image",
                        "archive_media",
                    ]
                ),
                narration_mode="voiceover",
                pacing=(
                    profile.pacing_strategy
                    if profile is not None
                    else "cinematic"
                ),
                reason=(
                    "Film explanation using the movie-facts "
                    "reference retention profile."
                ),
                rights_gate_required=True,
                reference_profile=profile_dict,
            )

        # ----------------------------------------------------
        # Explicit six-format identities
        # ----------------------------------------------------

        if genre == "cinematic_movie_edit":

            return ContentFormatDecision(
                format_name="cinematic_movie_edit",
                target_duration_min=profile.target_duration_min,
                target_duration_max=profile.target_duration_max,
                preferred_media=list(
                    profile.preferred_media
                ),
                narration_mode="minimal_commentary",
                pacing=profile.pacing_strategy,
                reason=(
                    "Cinematic movie-edit reference profile."
                ),
                rights_gate_required=True,
                reference_profile=profile_dict,
            )

        if genre == "curiosity_story":

            return ContentFormatDecision(
                format_name="documentary_story",
                target_duration_min=profile.target_duration_min,
                target_duration_max=profile.target_duration_max,
                preferred_media=list(
                    profile.preferred_media
                ),
                narration_mode="voiceover",
                pacing=profile.pacing_strategy,
                reason=(
                    "Curiosity-gap documentary reference profile."
                ),
                reference_profile=profile_dict,
            )

        if genre == "luxury_product":

            return ContentFormatDecision(
                format_name="visual_explainer",
                target_duration_min=profile.target_duration_min,
                target_duration_max=profile.target_duration_max,
                preferred_media=list(
                    profile.preferred_media
                ),
                narration_mode="voiceover",
                pacing=profile.pacing_strategy,
                reason=(
                    "Luxury/product reference profile."
                ),
                reference_profile=profile_dict,
            )

        if genre == "science_explainer":

            return ContentFormatDecision(
                format_name="visual_explainer",
                target_duration_min=profile.target_duration_min,
                target_duration_max=profile.target_duration_max,
                preferred_media=list(
                    profile.preferred_media
                ),
                narration_mode="voiceover",
                pacing=profile.pacing_strategy,
                reason=(
                    "Science/engineering visual-explanation "
                    "reference profile."
                ),
                reference_profile=profile_dict,
            )

        if genre == "business_wealth":

            return ContentFormatDecision(
                format_name="documentary_story",
                target_duration_min=profile.target_duration_min,
                target_duration_max=profile.target_duration_max,
                preferred_media=list(
                    profile.preferred_media
                ),
                narration_mode="voiceover",
                pacing=profile.pacing_strategy,
                reason=(
                    "Business/wealth causal-story reference profile."
                ),
                reference_profile=profile_dict,
            )

        # ----------------------------------------------------
        # Existing genre aliases
        # ----------------------------------------------------

        if genre in self.EXPLAINER_GENRES:

            return ContentFormatDecision(
                format_name="visual_explainer",
                target_duration_min=(
                    profile.target_duration_min
                    if profile is not None
                    else 35.0
                ),
                target_duration_max=(
                    profile.target_duration_max
                    if profile is not None
                    else 65.0
                ),
                preferred_media=(
                    list(profile.preferred_media)
                    if profile is not None
                    else [
                        "licensed_video",
                        "licensed_image",
                        "diagram",
                        "archive_media",
                    ]
                ),
                narration_mode="voiceover",
                pacing=(
                    profile.pacing_strategy
                    if profile is not None
                    else "information_density"
                ),
                reason=(
                    "Reference-style visual explainer."
                ),
                reference_profile=profile_dict,
            )

        if genre in self.STORY_GENRES:

            return ContentFormatDecision(
                format_name="documentary_story",
                target_duration_min=(
                    profile.target_duration_min
                    if profile is not None
                    else 40.0
                ),
                target_duration_max=(
                    profile.target_duration_max
                    if profile is not None
                    else 75.0
                ),
                preferred_media=(
                    list(profile.preferred_media)
                    if profile is not None
                    else [
                        "licensed_video",
                        "archive_media",
                        "licensed_image",
                        "documents",
                    ]
                ),
                narration_mode="voiceover",
                pacing=(
                    profile.pacing_strategy
                    if profile is not None
                    else "story_progression"
                ),
                reason=(
                    "Reference-style documentary story."
                ),
                reference_profile=profile_dict,
            )

        # ----------------------------------------------------
        # Conservative fallback
        # ----------------------------------------------------

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
            reference_profile=None,
        )
