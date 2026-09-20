"""Movie-title extraction for Rich V1 curated movie commentary."""

from __future__ import annotations


class MovieTopicParser:

    KNOWN_MOVIES = [
        "Doctor Strange",
        "Avengers Endgame",
        "Interstellar",
        "The Dark Knight",
        "Spider-Man No Way Home",
        "Inception",
        "Iron Man",
        "Jurassic Park",
        "The Matrix",
        "Pirates of the Caribbean",
    ]

    @classmethod
    def extract_movie_title(
        cls,
        topic: str,
    ) -> str | None:

        topic_lower = str(topic).lower()

        for movie in cls.KNOWN_MOVIES:

            if movie.lower() in topic_lower:
                return movie

        return None
