"""Safe 61–100 proposals and collision checks."""
import pytest

from backend.services.network.channel_blueprints import proposed_channels, validate_blueprints


def test_forty_distinct_safe_differentiated_proposals():
    proposed = proposed_channels()
    assert [p["number"] for p in proposed] == list(range(61, 101))
    assert len({p["editorial_identity"] for p in proposed}) == 40
    assert len({p["name"] for p in proposed}) == 40
    assert {p["format"] for p in proposed} == {
        "movie_facts", "cinematic_commentary", "curiosity_extreme",
        "luxury_product", "science_engineering", "business_wealth"}
    assert all(p["lifecycle_state"] == "PLANNED" and p["paused"]
               and p["max_daily_posts"] <= 2 and p["rights_strategy"]
               and p["allowed_topics"] and p["branding_specification"]["logo_prompt"]
               for p in proposed)
    assert validate_blueprints() == {"proposed": 40, "known_existing": 0,
                                      "all_100_checked": False, "missing_existing_roster": 60}


def test_actual_roster_collision_fails_and_unknown_roster_is_reported():
    with pytest.raises(ValueError, match="collision"):
        validate_blueprints([{"name": "OrbitMechanics", "handle": "@Existing"}])
    with pytest.raises(ValueError, match="too similar"):
        validate_blueprints([{"name": "OrbitMechanic", "handle": "@Different"}])
    assert validate_blueprints([{"name": "SpaceDecoded", "handle": "@SpaceDecoded"}])[
        "missing_existing_roster"] == 59
