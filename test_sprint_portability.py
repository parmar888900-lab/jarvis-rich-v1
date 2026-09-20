from unittest.mock import AsyncMock

import pytest

from backend.services.research.movie_research_service import MovieResearchService
from backend.services.video.movie_media_resolver import MovieMediaResolver


def test_movie_media_can_start_without_optional_pexels(monkeypatch):
    monkeypatch.delenv("PEXELS_API_KEY", raising=False)
    resolver = MovieMediaResolver()
    assert resolver.providers
    assert all(type(provider).__name__ != "PexelsProvider" for provider in resolver.providers)


def test_movie_research_prefers_construction_evidence_over_film_name():
    service = MovieResearchService()
    terms = service._angle_terms("Why Iron Man's first suit-building scene became iconic")
    terms.difference_update({"iron", "man"})
    result = service._extract_relevant_sentences(
        "Iron Man opened first at the box office. The Mark I armor was assembled in a cave.", terms)
    assert result == ["The Mark I armor was assembled in a cave."]


@pytest.mark.asyncio
async def test_public_release_requires_explicit_configuration(monkeypatch):
    from test_production_orchestrator import build_orchestrator, FakeCommander, FakeCycleService
    monkeypatch.delenv("JARVIS_PUBLIC_PUBLISH_ENABLED", raising=False)
    orchestrator = build_orchestrator(FakeCommander(), FakeCycleService())
    release = AsyncMock()
    orchestrator.release_service = release
    result = await orchestrator.run_cycle("private-only-test")
    assert result["status"] == "success"
    assert result["release"]["status"] == "disabled"
    release.release_cycle.assert_not_called()
