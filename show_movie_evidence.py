from backend.services.intelligence.movie_topic_parser import (
    MovieTopicParser,
)
from backend.services.research.movie_research_service import (
    MovieResearchService,
)

topic = (
    "Why Doctor Strange's mirror dimension "
    "scenes work so well"
)

movie = MovieTopicParser.extract_movie_title(topic)

service = MovieResearchService()

pack = service.research(
    movie_title=movie,
    commentary_topic=topic,
)

print("========== RESEARCH FACTS ==========")

for i, fact in enumerate(pack.facts, start=1):
    print()
    print(f"FACT {i}:")
    print(fact)
