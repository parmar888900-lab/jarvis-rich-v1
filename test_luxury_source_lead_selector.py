from backend.services.research.luxury_source_lead_selector import (
    LuxurySourceLeadSelector,
)


selector = LuxurySourceLeadSelector()

leads = selector.select(
    topic="Rolex Daytona",
    limit=12,
)

print()
print(
    "========== LUXURY SOURCE LEADS =========="
)

print(
    "TOTAL:",
    len(leads),
)

for index, lead in enumerate(
    leads,
    start=1,
):

    print()
    print(
        index,
        "|",
        lead.source_type,
        "| FINAL:",
        lead.final_score,
    )

    print(
        "CHANNEL:",
        lead.channel_title,
    )

    print(
        "TITLE:",
        lead.title,
    )

    print(
        "AUTH:",
        lead.authority_score,
        "| DISC:",
        lead.discovery_score,
        "| VIS:",
        lead.visual_positive_score,
        "| MARGIN:",
        lead.visual_margin,
    )

    print(
        "URL:",
        lead.watch_url,
    )
