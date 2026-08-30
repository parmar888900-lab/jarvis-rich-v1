import asyncio
from unittest.mock import patch

from backend.services.agent_handlers.youtube import (
    YoutubeAgentHandler,
)


class FakeGenerated:
    def to_dict(self):
        return {
            "title": "Fake generated content",
        }


class FakePipeline:
    def __init__(self):
        self.received_trend = None
        self.calls = 0

    async def run(self, trend):
        self.calls += 1
        self.received_trend = trend

        return {
            "generated": FakeGenerated(),
            "production_package": {
                "status": "fake",
            },
        }


class FakeManager:
    def __init__(self):
        self.providers = [
            "Fake YouTube",
            "Fake News",
        ]

    def collect_candidates(
        self,
        per_provider_limit=25,
    ):
        return [
            {"title": "raw-one"},
            {"title": "raw-two"},
        ]


class FakeEngine:
    def process(
        self,
        raw_trends,
        limit=10,
    ):
        assert len(raw_trends) == 2
        assert limit == 10

        return [
            {
                "title": "Extremely Viral Weak Topic",
                "source": "YouTube",
                "final_score": 99,
                "category": "General",
                "knowledge": {
                    "score": 10,
                    "summary": "",
                    "facts": [],
                    "sources": [],
                },
            },
            {
                "title": (
                    "Why researchers discovered "
                    "a major new technology"
                ),
                "source": "Google News RSS",
                "final_score": 80,
                "category": "News",
                "knowledge": {
                    "score": 90,
                    "summary": (
                        "A well-supported explanation."
                    ),
                    "facts": [
                        "Fact one.",
                        "Fact two.",
                        "Fact three.",
                    ],
                    "sources": [
                        {"source": "Source A"},
                        {"source": "Source B"},
                        {"source": "Source C"},
                    ],
                },
            },
        ]


async def main():
    handler = YoutubeAgentHandler()

    handler.engine = FakeEngine()

    fake_pipeline = FakePipeline()
    handler.pipeline = fake_pipeline

    fake_manager = FakeManager()

    with patch(
        "backend.services.agent_handlers.youtube."
        "build_trend_manager",
        return_value=fake_manager,
    ):
        result = await handler._analyze_trends(
            "test-command-001"
        )

    assert result["status"] == "success"

    assert result["command_id"] == (
        "test-command-001"
    )

    assert result["provider_count"] == 2
    assert result["raw_trend_count"] == 2
    assert result["final_trend_count"] == 2

    assert fake_pipeline.calls == 1

    assert (
        fake_pipeline.received_trend["title"]
        == "Why researchers discovered "
        "a major new technology"
    )

    assert (
        result["best_trend"]["title"]
        == fake_pipeline.received_trend["title"]
    )

    selection = result[
        "best_trend"
    ]["production_selection"]

    assert selection["eligible"] is True
    assert selection["selected"] is True

    print("=" * 70)
    print("REAL _analyze_trends ROUTING TEST")
    print()
    print(
        "STATUS:",
        result["status"],
    )
    print(
        "RAW TRENDS:",
        result["raw_trend_count"],
    )
    print(
        "RANKED TRENDS:",
        result["final_trend_count"],
    )
    print(
        "SELECTED:",
        result["best_trend"]["title"],
    )
    print(
        "PRODUCTION SCORE:",
        selection["production_score"],
    )
    print(
        "PIPELINE CALLS:",
        fake_pipeline.calls,
    )
    print()
    print(
        "PASS: actual _analyze_trends method "
        "routes the production-selected topic "
        "into VideoPipeline exactly once."
    )


asyncio.run(main())
