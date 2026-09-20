import asyncio

from backend.services.content_generator import ContentGenerator
from backend.services.intelligence.movie_topic_parser import (
    MovieTopicParser,
)
from backend.services.research.movie_research_service import (
    MovieResearchService,
)


async def main():

    topic = (
        "Why Doctor Strange's mirror dimension "
        "scenes work so well"
    )

    movie = MovieTopicParser.extract_movie_title(
        topic
    )

    research_service = MovieResearchService()

    pack = research_service.research(
        movie_title=movie,
        commentary_topic=topic,
    )

    research = (
        research_service.build_research_text(
            pack
        )
    )

    trend = {
        "title": topic,
        "genre": "famous_movie_commentary",
        "movie_title": movie,
        "research": research,
        "knowledge": pack.to_dict(),
        "content_format": {
            "format_name": "famous_movie_commentary",
        },
    }

    result = await ContentGenerator().generate(
        trend
    )

    print()
    print("========== MOVIE SCRIPT ==========")
    print("TITLE:", result.title)
    print("WORDS:", result.metadata.get("word_count"))

    print()

    for index, line in enumerate(
        result.script_lines,
        start=1,
    ):
        print(f"{index}: {line}")

    print()
    print(
        "EVIDENCE:",
        result.metadata.get("evidence_ids"),
    )

    print()
    print("HASHTAGS:", result.hashtags)


asyncio.run(main())

