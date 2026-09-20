from unittest.mock import AsyncMock

import pytest

from backend.services.research.movie_research_service import MovieResearchService


def test_movie_media_can_start_without_optional_pexels(monkeypatch):
    pytest.importorskip("torch")
    pytest.importorskip("open_clip")
    from backend.services.video.movie_media_resolver import MovieMediaResolver
    monkeypatch.delenv("PEXELS_API_KEY", raising=False)
    resolver = MovieMediaResolver()
    assert resolver.providers
    assert all(type(provider).__name__ != "PexelsProvider" for provider in resolver.providers)


def test_movie_research_prefers_construction_evidence_over_film_name():
    service = MovieResearchService()
    terms = service._angle_terms("Why Iron Man's first suit-building scene became iconic")
    terms.difference_update({"iron", "man"})
    result = service._extract_relevant_sentences(
        "Iron Man opened first at the box office. The Mark I armor was assembled in a cave.",
        terms,
        minimum_matches=2,
        excluded_phrases=service._angle_exclusions("suit-building"),
    )
    assert result == ["The Mark I armor was assembled in a cave."]


def test_movie_research_excludes_other_armor_from_mark_one_angle():
    service = MovieResearchService()
    terms = service._angle_terms("Why Iron Man's first suit-building scene became iconic")
    result = service._extract_relevant_sentences(
        "Stan Winston built the Iron Monger armor. Yinsen helps Stark build the first Iron Man suit in the cave.",
        terms,
        minimum_matches=2,
        excluded_phrases=service._angle_exclusions("suit-building"),
    )
    assert result == ["Yinsen helps Stark build the first Iron Man suit in the cave."]


@pytest.mark.asyncio
async def test_public_release_requires_explicit_configuration(monkeypatch):
    pytest.importorskip("torch")
    pytest.importorskip("open_clip")
    from test_production_orchestrator import build_orchestrator, FakeCommander, FakeCycleService
    monkeypatch.delenv("JARVIS_PUBLIC_PUBLISH_ENABLED", raising=False)
    orchestrator = build_orchestrator(FakeCommander(), FakeCycleService())
    release = AsyncMock()
    orchestrator.release_service = release
    result = await orchestrator.run_cycle("private-only-test")
    assert result["status"] == "success"
    assert result["release"]["status"] == "disabled"
    release.release_cycle.assert_not_called()
