"""
Reference-format production profiles for Jarvis Rich V1.

These profiles describe the retention mechanics, narrative progression,
visual density, pacing, and failure modes of Jarvis's six production
formats.

They do not authorize media and do not weaken factual, evidence,
copyright, or provenance validation.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True, slots=True)
class ReferenceFormatProfile:
    format_name: str

    viewer_mechanism: str
    hook_strategy: str
    story_progression: tuple[str, str, str, str]
    payoff_strategy: str

    narration_style: str
    narration_density: str

    target_duration_min: float
    target_duration_max: float

    target_visual_beats_min: int
    target_visual_beats_max: int

    target_shot_duration_min: float
    target_shot_duration_max: float

    visual_strategy: str
    pacing_strategy: str

    preferred_media: tuple[str, ...]

    forbidden_patterns: tuple[str, ...]

    rights_gate_required: bool = False

    def to_dict(self) -> dict:
        data = asdict(self)

        # JSON-friendly output and compatibility with callers that
        # expect lists instead of tuples.
        data["story_progression"] = list(
            self.story_progression
        )
        data["preferred_media"] = list(
            self.preferred_media
        )
        data["forbidden_patterns"] = list(
            self.forbidden_patterns
        )

        return data


REFERENCE_FORMAT_PROFILES: dict[
    str,
    ReferenceFormatProfile,
] = {

    # ========================================================
    # 1. MOVIE FACTS
    # ========================================================

    "movie_facts": ReferenceFormatProfile(
        format_name="movie_facts",

        viewer_mechanism=(
            "Recognition plus a surprising, concrete detail about "
            "a known film, scene, character, production decision, "
            "or filmmaking technique."
        ),

        hook_strategy=(
            "Open on the recognizable movie-specific subject and "
            "immediately introduce the unexpected detail. Avoid "
            "generic trivia framing."
        ),

        story_progression=(
            "recognizable_specific_hook",
            "minimum_required_context",
            "strongest_grounded_movie_detail",
            "why_the_detail_matters",
        ),

        payoff_strategy=(
            "End by resolving why the researched detail changes the "
            "viewer’s understanding of the scene, technique, or "
            "production decision."
        ),

        narration_style=(
            "Fast cinematic commentary with concrete nouns, specific "
            "details, and minimal setup."
        ),

        narration_density="high_information_density",

        target_duration_min=32.0,
        target_duration_max=55.0,

        target_visual_beats_min=9,
        target_visual_beats_max=14,

        target_shot_duration_min=1.5,
        target_shot_duration_max=3.5,

        visual_strategy=(
            "Prioritize exact movie-relevant authorized imagery, "
            "filmmaking context, production material, VFX context, "
            "and detail shots that directly support narration."
        ),

        pacing_strategy=(
            "Immediate recognizable opening, frequent visual changes, "
            "then slightly longer hold on the strongest proof/detail."
        ),

        preferred_media=(
            "authorized_movie_excerpt",
            "licensed_promotional_media",
            "licensed_image",
            "archive_media",
        ),

        forbidden_patterns=(
            "generic_did_you_know_hook",
            "unsupported_movie_trivia",
            "generic_stock_visuals",
            "unrelated_movie_imagery",
            "unsupported_audience_reaction",
            "school_report_narration",
            "generic_call_to_action",
        ),

        rights_gate_required=True,
    ),


    # ========================================================
    # 2. CINEMATIC MOVIE EDIT
    # ========================================================

    "cinematic_movie_edit": ReferenceFormatProfile(
        format_name="cinematic_movie_edit",

        viewer_mechanism=(
            "Recognition, emotion, spectacle, rhythm, and escalating "
            "visual intensity built around one coherent movie subject."
        ),

        hook_strategy=(
            "Cold-open with the strongest immediately understandable "
            "visual or dramatic moment rather than explanatory setup."
        ),

        story_progression=(
            "high_impact_cold_open",
            "visual_or_emotional_escalation",
            "peak_sequence",
            "clean_visual_payoff",
        ),

        payoff_strategy=(
            "Finish on the strongest coherent visual or emotional beat "
            "instead of adding explanatory filler."
        ),

        narration_style=(
            "Minimal commentary when narration is necessary; visuals, "
            "sound, rhythm, and sequencing should carry more weight."
        ),

        narration_density="low_to_medium",

        target_duration_min=20.0,
        target_duration_max=45.0,

        target_visual_beats_min=10,
        target_visual_beats_max=16,

        target_shot_duration_min=0.8,
        target_shot_duration_max=2.8,

        visual_strategy=(
            "Use coherent authorized material from the same movie or "
            "subject with deliberate wide, medium, close, detail, "
            "movement, reaction, and payoff variation."
        ),

        pacing_strategy=(
            "Fast opening cuts, escalating rhythm through the middle, "
            "strongest sequence near the peak, decisive ending."
        ),

        preferred_media=(
            "authorized_movie_excerpt",
            "licensed_promotional_media",
            "licensed_movie_video",
            "licensed_image",
        ),

        forbidden_patterns=(
            "random_movie_montage",
            "unrelated_stock_footage",
            "excessive_exposition",
            "repeated_identical_shots",
            "weak_opening_frame",
            "rights_unverified_movie_media",
            "generic_call_to_action",
        ),

        rights_gate_required=True,
    ),


    # ========================================================
    # 3. CURIOSITY STORY
    # ========================================================

    "curiosity_story": ReferenceFormatProfile(
        format_name="curiosity_story",

        viewer_mechanism=(
            "An information gap: the viewer sees an unusual event, "
            "object, place, decision, or outcome and wants the missing "
            "explanation."
        ),

        hook_strategy=(
            "Lead with the abnormal or unexplained result before giving "
            "the explanation. Create a concrete unanswered question."
        ),

        story_progression=(
            "abnormal_event_or_result",
            "essential_context_and_stakes",
            "causal_escalation",
            "explanation_or_reveal",
        ),

        payoff_strategy=(
            "Close the information gap with a concrete reveal or causal "
            "explanation rather than an abstract conclusion."
        ),

        narration_style=(
            "Direct documentary storytelling with short causal steps "
            "and constant forward movement."
        ),

        narration_density="medium_high",

        target_duration_min=30.0,
        target_duration_max=55.0,

        target_visual_beats_min=9,
        target_visual_beats_max=14,

        target_shot_duration_min=1.4,
        target_shot_duration_max=3.5,

        visual_strategy=(
            "Show the real subject, location, event, object, documents, "
            "or process whenever authorized media exists. Visuals must "
            "advance the explanation rather than decorate it."
        ),

        pacing_strategy=(
            "Fast hook, controlled context, progressively more specific "
            "visual evidence, then a clearly staged reveal."
        ),

        preferred_media=(
            "licensed_video",
            "archive_media",
            "licensed_image",
            "documents",
        ),

        forbidden_patterns=(
            "answer_revealed_in_first_sentence",
            "generic_stock_people",
            "unrelated_cinematic_filler",
            "fake_mystery_language",
            "unsupported_sensationalism",
            "repetitive_visuals",
            "generic_call_to_action",
        ),
    ),


    # ========================================================
    # 4. LUXURY / PRODUCT
    # ========================================================

    "luxury_product": ReferenceFormatProfile(
        format_name="luxury_product",

        viewer_mechanism=(
            "Desire plus specificity: show an object that looks valuable "
            "or unusual, then explain the craftsmanship, engineering, "
            "scarcity, material, or mechanism behind that value."
        ),

        hook_strategy=(
            "Open with the actual product or its most visually distinctive "
            "detail and immediately establish what makes it unusual."
        ),

        story_progression=(
            "object_first_hook",
            "why_it_is_unusual",
            "mechanism_material_or_craft",
            "value_or_design_payoff",
        ),

        payoff_strategy=(
            "End on the concrete engineering, craftsmanship, material, "
            "design, scarcity, or functional reason the object stands out."
        ),

        narration_style=(
            "Precise premium product commentary. Concrete details should "
            "replace vague luxury adjectives."
        ),

        narration_density="medium_high",

        target_duration_min=28.0,
        target_duration_max=50.0,

        target_visual_beats_min=10,
        target_visual_beats_max=15,

        target_shot_duration_min=1.2,
        target_shot_duration_max=3.2,

        visual_strategy=(
            "Prioritize the exact model or product: hero view, close "
            "detail, material, mechanism, craftsmanship, operation, "
            "scale, and contextual use."
        ),

        pacing_strategy=(
            "Strong product reveal, rapid detail progression, slower "
            "holds for craftsmanship or mechanisms, polished payoff."
        ),

        preferred_media=(
            "licensed_product_video",
            "licensed_video",
            "licensed_image",
            "archive_media",
            "diagram",
        ),

        forbidden_patterns=(
            "generic_rich_lifestyle_stock",
            "wrong_product_model",
            "unverified_price_claim",
            "empty_luxury_adjectives",
            "repeated_product_angle",
            "unrelated_supercar_or_money_filler",
            "generic_call_to_action",
        ),
    ),


    # ========================================================
    # 5. SCIENCE / ENGINEERING EXPLAINER
    # ========================================================

    "science_explainer": ReferenceFormatProfile(
        format_name="science_explainer",

        viewer_mechanism=(
            "Visual understanding: begin with an impressive result, "
            "then make the hidden mechanism or process understandable."
        ),

        hook_strategy=(
            "Show or describe the surprising result first, then pose "
            "the mechanism as the missing explanation."
        ),

        story_progression=(
            "surprising_result",
            "core_mechanism",
            "process_or_component_sequence",
            "real_world_consequence",
        ),

        payoff_strategy=(
            "Finish by connecting the mechanism to the visible result "
            "or practical consequence introduced at the beginning."
        ),

        narration_style=(
            "Clear technical explanation using concrete mechanisms, "
            "objects, forces, components, and causal language."
        ),

        narration_density="high_information_density",

        target_duration_min=32.0,
        target_duration_max=58.0,

        target_visual_beats_min=10,
        target_visual_beats_max=15,

        target_shot_duration_min=1.4,
        target_shot_duration_max=3.4,

        visual_strategy=(
            "Use mechanism-specific footage, real demonstrations, "
            "exteriors, internal components, process stages, diagrams, "
            "and operation footage directly tied to each claim."
        ),

        pacing_strategy=(
            "Fast result hook followed by ordered visual explanation. "
            "Each major causal step should trigger a visual change."
        ),

        preferred_media=(
            "licensed_video",
            "licensed_image",
            "diagram",
            "archive_media",
        ),

        forbidden_patterns=(
            "generic_science_stock",
            "unrelated_lab_footage",
            "mechanism_not_shown",
            "unsupported_technical_claim",
            "visuals_that_contradict_narration",
            "school_report_opening",
            "generic_call_to_action",
        ),
    ),


    # ========================================================
    # 6. BUSINESS / WEALTH STORY
    # ========================================================

    "business_wealth": ReferenceFormatProfile(
        format_name="business_wealth",

        viewer_mechanism=(
            "Money plus causality: begin with a surprising business "
            "outcome, then explain the decision, product, constraint, "
            "or strategy that produced it."
        ),

        hook_strategy=(
            "Open with a specific surprising outcome, scale, business "
            "decision, or contradiction instead of generic wealth imagery."
        ),

        story_progression=(
            "surprising_business_outcome",
            "origin_or_constraint",
            "decisive_move_or_mechanism",
            "scale_and_consequence",
        ),

        payoff_strategy=(
            "End with the concrete consequence of the business decision "
            "or mechanism introduced in the story."
        ),

        narration_style=(
            "Compressed documentary/business storytelling with specific "
            "companies, products, decisions, numbers, and causal links "
            "when those facts are grounded."
        ),

        narration_density="high_information_density",

        target_duration_min=32.0,
        target_duration_max=58.0,

        target_visual_beats_min=9,
        target_visual_beats_max=14,

        target_shot_duration_min=1.4,
        target_shot_duration_max=3.5,

        visual_strategy=(
            "Use the real company, founder, product, factory, headquarters, "
            "documents, historical context, or mechanism behind the claim."
        ),

        pacing_strategy=(
            "Outcome-first hook, rapid context, concrete causal sequence, "
            "then scale or consequence as the payoff."
        ),

        preferred_media=(
            "licensed_video",
            "archive_media",
            "licensed_image",
            "documents",
        ),

        forbidden_patterns=(
            "generic_money_stock",
            "generic_business_people",
            "unsupported_net_worth_claim",
            "unsupported_revenue_claim",
            "motivational_filler",
            "fake_success_causality",
            "generic_call_to_action",
        ),
    ),
}


FORMAT_ALIASES: dict[str, str] = {
    "movie_facts": "movie_facts",
    "scene_breakdowns": "movie_facts",
    "movies_filmmaking": "movie_facts",
    "famous_movie_commentary": "movie_facts",

    "cinematic_movie_edit": "cinematic_movie_edit",

    "curiosity_story": "curiosity_story",
    "history_inventions": "curiosity_story",
    "human_performance": "curiosity_story",

    "luxury_product": "luxury_product",
    "interesting_products": "luxury_product",
    "luxury_money": "luxury_product",

    "science_explainer": "science_explainer",
    "science_engineering": "science_explainer",
    "technology": "science_explainer",
    "machines_manufacturing": "science_explainer",
    "space_aviation": "science_explainer",

    "business_wealth": "business_wealth",
    "business_stories": "business_wealth",
}


def resolve_reference_format(
    value: str,
) -> str | None:
    key = str(value or "").strip().lower()

    if not key:
        return None

    if key in REFERENCE_FORMAT_PROFILES:
        return key

    return FORMAT_ALIASES.get(key)


def get_reference_profile(
    value: str,
) -> ReferenceFormatProfile | None:
    resolved = resolve_reference_format(value)

    if resolved is None:
        return None

    return REFERENCE_FORMAT_PROFILES.get(
        resolved
    )


def get_reference_profile_dict(
    value: str,
) -> dict | None:
    profile = get_reference_profile(value)

    if profile is None:
        return None

    return profile.to_dict()
