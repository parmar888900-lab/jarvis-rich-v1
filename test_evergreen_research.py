from backend.services.research.evergreen_research_service import (
    EvergreenResearchService,
)

service = EvergreenResearchService()

pack = service.research(
    "Why train wheels are shaped differently from car wheels"
)

print("TOPIC:", pack.topic)
print("SCORE:", pack.score)
print("SOURCES:", len(pack.sources))
print("FACTS:", len(pack.facts))
print()
print("SUMMARY:")
print(pack.summary[:1500])
