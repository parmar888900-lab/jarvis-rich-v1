"""Safe 61–100 proposals and collision checks."""
import json
from pathlib import Path

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


def test_owner_supplied_account_roster_checks_all_one_hundred_without_registration():
    roster = json.loads((Path(__file__).parent / "config" /
                         "channel_roster_1_60.user_supplied.json").read_text(encoding="utf-8"))
    assert len(roster) == 60
    assert roster[12] == {"name": "SpaceDecoded", "handle": "@SpaceDecoded-s5d"}
    assert roster[58] == {"name": "BatteryDecoded", "handle": "@BatteryDecoded-v1q"}
    assert validate_blueprints(roster) == {
        "proposed": 40, "known_existing": 60,
        "all_100_checked": True, "missing_existing_roster": 0,
    }
    proposals = proposed_channels()
    assert proposals[3]["name"] == "CellChemistryLab"
    assert len({p["niche"] for p in proposals}) == 40
    assert len({p["editorial_identity"] for p in proposals}) == 40
    assert len({p["handle_candidate"].casefold() for p in proposals}) == 40
    assert len({tuple(p["allowed_topics"]) for p in proposals}) == 40
    assert all(not set(p["allowed_topics"]) & set(p["blocked_topics"])
               and p["production_engine"] == "rich_v1"
               and p["lifecycle_state"] == "PLANNED" and p["paused"]
               and 0 <= p["max_daily_posts"] <= 4
               for p in proposals)
