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

movie = MovieTopicParser.extract_movie_title(
    topic
)

print("MOVIE:", movie)

service = MovieResearchService()

pack = service.research(
    movie_title=movie,
    commentary_topic=topic,
)

print("SOURCES:", len(pack.sources))
print("FACTS:", len(pack.facts))
print("SCORE:", pack.score)

print()
print("SUMMARY:")
print(pack.summary[:2000])
