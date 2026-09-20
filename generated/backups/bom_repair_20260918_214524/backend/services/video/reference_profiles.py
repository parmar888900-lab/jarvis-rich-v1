"""Canonical Rich V1 production profiles.

These profiles encode the editing grammar of the six benchmark
formats used by Jarvis Rich V1.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict


@dataclass(frozen=True, slots=True)
class RichFormatProfile:
    format_name: str
    benchmark_reference: str

    target_duration: float
    min_duration: float
    max_duration: float

    width: int
    height: int
    fps: int

    min_shot_duration: float
    target_shot_duration: float
    max_shot_duration: float

    hook_duration: float

    captions_enabled: bool
    words_per_caption: int
    caption_font_size: int
    caption_y: int
    caption_width: int
    caption_emphasis: bool

    narration_enabled: bool
    music_enabled: bool
    original_source_audio: bool

    zoom_enabled: bool
    dynamic_reframe: bool
    speed_variation: bool

    hard_cut_bias: float
    transition_bias: float

    preferred_video_ratio: float

    visual_strategy: str
    pacing_style: str

    def to_dict(self) -> dict:
        return asdict(self)


PROFILES = {

    ########################################################
    # 1. MOVIE / SUPERHERO FACT COMMENTARY
    ########################################################

    "movie_facts": RichFormatProfile(
        format_name="movie_facts",
        benchmark_reference="11753.mp4",

        target_duration=37.0,
        min_duration=32.0,
        max_duration=45.0,

        width=1080,
        height=1920,
        fps=60,

        min_shot_duration=0.8,
        target_shot_duration=1.7,
        max_shot_duration=3.0,

        hook_duration=2.5,

        captions_enabled=True,
        words_per_caption=3,
        caption_font_size=82,
        caption_y=1060,
        caption_width=880,
        caption_emphasis=True,

        narration_enabled=True,
        music_enabled=True,
        original_source_audio=False,

        zoom_enabled=True,
        dynamic_reframe=True,
        speed_variation=True,

        hard_cut_bias=0.85,
        transition_bias=0.15,

        preferred_video_ratio=0.95,

        visual_strategy=(
            "movie_scene_driven_commentary"
        ),
        pacing_style=(
            "fast_information_dense"
        ),
    ),

    ########################################################
    # 2. CINEMATIC MOVIE EDIT
    ########################################################

    "cinematic_movie_edit": RichFormatProfile(
        format_name="cinematic_movie_edit",
        benchmark_reference="11754.mp4",

        target_duration=57.9,
        min_duration=48.0,
        max_duration=65.0,

        width=1080,
        height=1920,
        fps=60,

        min_shot_duration=0.45,
        target_shot_duration=1.35,
        max_shot_duration=3.2,

        hook_duration=1.5,

        captions_enabled=False,
        words_per_caption=0,
        caption_font_size=0,
        caption_y=0,
        caption_width=0,
        caption_emphasis=False,

        narration_enabled=False,
        music_enabled=True,
        original_source_audio=True,

        zoom_enabled=True,
        dynamic_reframe=True,
        speed_variation=True,

        hard_cut_bias=0.70,
        transition_bias=0.30,

        preferred_video_ratio=1.0,

        visual_strategy=(
            "cinematic_scene_montage"
        ),
        pacing_style=(
            "music_driven_emotional"
        ),
    ),

    ########################################################
    # 3. CURIOSITY / EXTREME STORY
    ########################################################

    "curiosity_story": RichFormatProfile(
        format_name="curiosity_story",
        benchmark_reference="11755.mp4",

        target_duration=55.4,
        min_duration=48.0,
        max_duration=62.0,

        width=1080,
        height=1920,
        fps=60,

        min_shot_duration=0.9,
        target_shot_duration=1.8,
        max_shot_duration=3.2,

        hook_duration=2.2,

        captions_enabled=True,
        words_per_caption=3,
        caption_font_size=80,
        caption_y=1050,
        caption_width=880,
        caption_emphasis=True,

        narration_enabled=True,
        music_enabled=True,
        original_source_audio=False,

        zoom_enabled=True,
        dynamic_reframe=True,
        speed_variation=False,

        hard_cut_bias=0.90,
        transition_bias=0.10,

        preferred_video_ratio=0.90,

        visual_strategy=(
            "real_world_story_broll"
        ),
        pacing_style=(
            "high_retention_curiosity"
        ),
    ),

    ########################################################
    # 4. LUXURY / PRODUCT EXPLAINER
    ########################################################

    "luxury_product": RichFormatProfile(
        format_name="luxury_product",
        benchmark_reference="11756.mp4",

        target_duration=73.0,
        min_duration=62.0,
        max_duration=80.0,

        width=1080,
        height=1920,
        fps=60,

        min_shot_duration=1.0,
        target_shot_duration=2.1,
        max_shot_duration=4.0,

        hook_duration=2.5,

        captions_enabled=True,
        words_per_caption=3,
        caption_font_size=76,
        caption_y=1080,
        caption_width=860,
        caption_emphasis=True,

        narration_enabled=True,
        music_enabled=True,
        original_source_audio=False,

        zoom_enabled=True,
        dynamic_reframe=True,
        speed_variation=False,

        hard_cut_bias=0.75,
        transition_bias=0.25,

        preferred_video_ratio=0.90,

        visual_strategy=(
            "premium_product_detail"
        ),
        pacing_style=(
            "premium_information_dense"
        ),
    ),

    ########################################################
    # 5. SCIENCE / ENGINEERING EXPLAINER
    ########################################################

    "science_explainer": RichFormatProfile(
        format_name="science_explainer",
        benchmark_reference="11757.mp4",

        target_duration=42.9,
        min_duration=36.0,
        max_duration=50.0,

        width=1080,
        height=1920,
        fps=60,

        min_shot_duration=0.8,
        target_shot_duration=1.65,
        max_shot_duration=3.0,

        hook_duration=2.0,

        captions_enabled=True,
        words_per_caption=3,
        caption_font_size=78,
        caption_y=1050,
        caption_width=870,
        caption_emphasis=True,

        narration_enabled=True,
        music_enabled=True,
        original_source_audio=False,

        zoom_enabled=True,
        dynamic_reframe=True,
        speed_variation=False,

        hard_cut_bias=0.85,
        transition_bias=0.15,

        preferred_video_ratio=0.90,

        visual_strategy=(
            "demonstration_and_explanation"
        ),
        pacing_style=(
            "visual_explanation_dense"
        ),
    ),

    ########################################################
    # 6. BUSINESS / WEALTH STORY
    ########################################################

    "business_wealth": RichFormatProfile(
        format_name="business_wealth",
        benchmark_reference="11758.mp4",

        target_duration=74.6,
        min_duration=64.0,
        max_duration=82.0,

        width=1080,
        height=1920,
        fps=60,

        min_shot_duration=1.0,
        target_shot_duration=2.0,
        max_shot_duration=3.8,

        hook_duration=2.5,

        captions_enabled=True,
        words_per_caption=3,
        caption_font_size=78,
        caption_y=1060,
        caption_width=880,
        caption_emphasis=True,

        narration_enabled=True,
        music_enabled=True,
        original_source_audio=False,

        zoom_enabled=True,
        dynamic_reframe=True,
        speed_variation=False,

        hard_cut_bias=0.85,
        transition_bias=0.15,

        preferred_video_ratio=0.85,

        visual_strategy=(
            "documentary_business_story"
        ),
        pacing_style=(
            "documentary_high_retention"
        ),
    ),
}


ALIASES = {
    "famous_movie_commentary": "movie_facts",
    "movie_commentary": "movie_facts",
    "movie_edit": "cinematic_movie_edit",
    "cinematic_edit": "cinematic_movie_edit",
    "curiosity": "curiosity_story",
    "extreme_story": "curiosity_story",
    "luxury": "luxury_product",
    "product": "luxury_product",
    "science": "science_explainer",
    "engineering": "science_explainer",
    "business": "business_wealth",
    "wealth": "business_wealth",
}


def get_profile(
    format_name: str,
) -> RichFormatProfile:

    clean = str(
        format_name
    ).strip().lower()

    clean = ALIASES.get(
        clean,
        clean,
    )

    if clean not in PROFILES:
        raise KeyError(
            f"Unknown Rich V1 format profile: {format_name}"
        )

    return PROFILES[clean]
