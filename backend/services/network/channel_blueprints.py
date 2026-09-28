"""Unregistered editorial blueprints for channels 61–100.

These are proposals, not YouTube accounts or active NetworkChannel rows. A
human must check existing accounts and rights before any activation.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher


# Number, name, niche, production format, allowed topic, editorial promise,
# visual identity. Deliberately narrow topic terms prevent a generic channel
# from silently accepting unrelated trending material.
BLUEPRINTS = (
    (61, "OrbitMechanics", "space engineering", "science_engineering", "orbital mechanics", "Explain orbital maneuvers with mission geometry and measured constraints", "indigo orbital arcs"),
    (62, "OceanMachines", "marine engineering", "science_engineering", "submersible", "Explain underwater vehicle mechanisms using documented engineering", "teal bathymetric lines"),
    (63, "BridgeLogic", "civil engineering", "science_engineering", "bridge engineering", "Trace the load path through one bridge design at a time", "copper structural grids"),
    (64, "CellChemistryLab", "energy engineering", "science_engineering", "battery chemistry", "Explain storage chemistry through verified failure and design tradeoffs", "amber cell schematics"),
    (65, "DeepEarthLab", "geoscience", "science_engineering", "seismology", "Explain seismic measurements and Earth's interior from published observations", "ochre strata contours"),
    (66, "FlightControlLab", "aviation engineering", "science_engineering", "aircraft control", "Show how flight controls solve documented aerodynamic problems", "sky-blue airflow ribbons"),
    (67, "ParticleLedger", "physics", "science_engineering", "particle detector", "Translate detector evidence into understandable particle observations", "violet detector rings"),
    (68, "WaterWorksLab", "water infrastructure", "science_engineering", "water treatment", "Follow water through verified treatment mechanisms and constraints", "aqua flow diagrams"),
    (69, "SurvivalMargins", "extreme environments", "curiosity_extreme", "survival physiology", "Explain documented human survival limits without sensational claims", "rust thermal contours"),
    (70, "StormAnatomy", "severe weather", "curiosity_extreme", "storm formation", "Investigate why a verified storm intensified using measured weather data", "electric-blue isobars"),
    (71, "CaveFrontiers", "cave science", "curiosity_extreme", "cave exploration", "Tell documented cave discoveries through geology and expedition evidence", "limestone depth maps"),
    (72, "VolcanoSignals", "volcanology", "curiosity_extreme", "volcano monitoring", "Decode eruption warning signals with observatory records", "lava-orange seismic traces"),
    (73, "PolarFieldnotes", "polar expeditions", "curiosity_extreme", "polar expedition", "Reconstruct evidence-backed polar field challenges and discoveries", "ice-white route lines"),
    (74, "DeepSeaOddities", "ocean biology", "curiosity_extreme", "deep sea biology", "Explain documented deep-sea adaptations and their evidence", "bioluminescent cyan silhouettes"),
    (75, "DesertThreshold", "desert science", "curiosity_extreme", "desert adaptation", "Explore measured survival strategies in arid ecosystems", "sand-gold heat maps"),
    (76, "AncientMechanisms", "archaeology", "curiosity_extreme", "ancient mechanism", "Explain archaeological mechanisms from excavated evidence", "bronze artifact outlines"),
    (77, "WatchmakingInside", "horology", "luxury_product", "mechanical watch", "Explain watch complications through maker specifications and mechanism views", "silver gear macro"),
    (78, "AudioEngineeringLab", "premium audio", "luxury_product", "headphone engineering", "Compare documented transducer design choices without unverified superlatives", "graphite acoustic waves"),
    (79, "CameraCraft", "imaging products", "luxury_product", "camera optics", "Explain lens and sensor design from verified product specifications", "prism-purple optical rays"),
    (80, "ElectricGrandTour", "electric vehicles", "luxury_product", "electric vehicle design", "Show engineering tradeoffs in documented premium EV systems", "emerald drivetrain paths"),
    (81, "ArchitecturalObjects", "design objects", "luxury_product", "furniture design", "Explain the material and fabrication behind iconic furniture designs", "walnut joinery details"),
    (82, "SailcraftDesign", "yacht engineering", "luxury_product", "sailing yacht design", "Explain sail and hull choices using builder and class evidence", "navy hydrodynamic lines"),
    (83, "SupplyChainStories", "commerce", "business_wealth", "supply chain", "Trace documented bottlenecks and incentives in one supply chain", "amber route nodes"),
    (84, "MarketMechanisms", "market structure", "business_wealth", "market structure", "Explain exchange mechanisms from public rules and data", "cyan order-book ladders"),
    (85, "FoundersLedger", "company history", "business_wealth", "company founding", "Tell verifiable founder decisions through filings and primary interviews", "slate milestone timelines"),
    (86, "PatentEconomics", "innovation economics", "business_wealth", "patent licensing", "Explain documented licensing models and their economic effects", "cobalt document layers"),
    (87, "FactoryNumbers", "manufacturing economics", "business_wealth", "manufacturing cost", "Unpack measured factory cost structures without invented margins", "steel production diagrams"),
    (88, "CityFinance", "urban economics", "business_wealth", "municipal finance", "Explain public budgets and infrastructure funding with official records", "gold city grids"),
    (89, "FrameFacts", "film production facts", "movie_facts", "film production design", "Verify practical production design decisions from authorized sources", "crimson storyboard frames"),
    (90, "SoundstageSecrets", "film craft", "movie_facts", "film sound design", "Explain documented soundstage techniques without unlicensed clips", "magenta waveform slates"),
    (91, "CostumeEvidence", "film costume craft", "movie_facts", "film costume design", "Trace credited costume choices through production evidence", "burgundy fabric swatches"),
    (92, "MiniatureCinema", "practical effects", "movie_facts", "film miniature effects", "Document miniature techniques with cleared behind-the-scenes media", "copper model blueprints"),
    (93, "CreditsDecoded", "film crews", "movie_facts", "film crew roles", "Explain credited crew contributions using official materials", "silver credit typography"),
    (94, "LocationLens", "film locations", "movie_facts", "film location scouting", "Explain verified location choices and production constraints", "carmine map overlays"),
    (95, "SceneGrammar", "cinematic analysis", "cinematic_commentary", "film blocking", "Analyze documented blocking choices using rights-cleared illustrative media", "blue shot vectors"),
    (96, "EditRoomNotes", "film editing", "cinematic_commentary", "film editing technique", "Explain editing rhythm with original diagrams or licensed excerpts", "red timeline markers"),
    (97, "LightMotivated", "cinematography", "cinematic_commentary", "film lighting technique", "Examine lighting setups from credited interviews and permitted media", "amber light cones"),
    (98, "CameraMovementLab", "camera craft", "cinematic_commentary", "film camera movement", "Explain camera-movement intent with original motion diagrams", "teal camera tracks"),
    (99, "ColorStoryLab", "color grading", "cinematic_commentary", "film color grading", "Analyze color decisions with authorized examples and original graphics", "spectrum color wheels"),
    (100, "DialogueCut", "scene construction", "cinematic_commentary", "film dialogue editing", "Explain reaction and dialogue editing with original staged examples", "violet dialogue beats"),
)

RIGHTS_POLICIES = {
    "movie_facts": "Only official or explicitly licensed production media; original diagrams otherwise. No ripping or DRM bypass.",
    "cinematic_commentary": "Use cleared excerpts only with documented usage basis; prefer original staged demonstrations and diagrams.",
    "curiosity_extreme": "Use primary institutional archives or explicitly licensed footage with source attribution.",
    "luxury_product": "Use manufacturer-cleared media, licensed stock, or original diagrams; verify product claims.",
    "science_engineering": "Prefer authoritative agency, lab, or manufacturer material with recorded usage basis.",
    "business_wealth": "Use public filings and licensed visual assets; never imply unverified financial outcomes.",
}


def proposed_channels() -> list[dict]:
    proposals = []
    for number, name, niche, format_name, topic, editorial, motif in BLUEPRINTS:
        proposals.append({
            "number": number, "name": name, "handle_candidate": "@" + name,
            "niche": niche, "production_engine": "rich_v1",
            "format": format_name, "editorial_identity": editorial,
            "topic_universe": [topic], "allowed_topics": [topic],
            "blocked_topics": ["unverified rumor", "unlicensed footage"],
            "max_daily_posts": 1 if format_name in {"movie_facts", "cinematic_commentary"} else 2,
            "lifecycle_state": "PLANNED", "paused": True,
            "branding_specification": {
                "motif": motif,
                "logo_prompt": f"Original geometric emblem for {name}, {motif}, no third-party marks or text",
                "banner_prompt": f"Original editorial banner for {name}, {motif}, legible safe area, no third-party marks",
            },
            "rights_strategy": RIGHTS_POLICIES[format_name],
        })
    return proposals


def validate_blueprints(existing: list[dict] | None = None) -> dict:
    """Check candidates against known account/registry names; report missing roster.

    `existing` is an actual supplied roster, never a fabricated first-60 list.
    """
    proposals = proposed_channels()
    if [item["number"] for item in proposals] != list(range(61, 101)):
        raise ValueError("Expected exactly the numbered 61–100 blueprints")
    known = existing or []
    all_entries = known + proposals
    if any(not isinstance(item, dict) or not item.get("name") for item in known):
        raise ValueError("Existing roster needs real channel names")
    seen: dict[str, str] = {}
    for index, item in enumerate(all_entries):
        for value in (item["name"], item.get("handle") or item.get("handle_candidate")):
            if not value:
                continue
            key = re.sub(r"[^a-z0-9]", "", value.casefold())
            if key in seen and seen[key][0] != index:
                raise ValueError(f"Channel name/handle collision: {value} and {seen[key]}")
            seen[key] = (index, value)
    for index, left in enumerate(all_entries):
        for right_index in range(index + 1, len(all_entries)):
            # Existing account names are owner-supplied facts, not proposals
            # this validator is authorized to rename. Flag only comparisons
            # involving a proposed channel.
            if right_index < len(known):
                continue
            right = all_entries[right_index]
            a, b = left["name"].casefold(), right["name"].casefold()
            if SequenceMatcher(None, a, b).ratio() >= .88:
                raise ValueError(f"Channel names too similar: {left['name']} and {right['name']}")
    return {"proposed": len(proposals), "known_existing": len(known),
            "all_100_checked": len(known) == 60,
            "missing_existing_roster": max(0, 60 - len(known))}
