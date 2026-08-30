import asyncio
from unittest.mock import patch

from backend.services.agent_handlers.youtube import YoutubeAgentHandler


class FakePipeline:
    def __init__(self):
        self.calls = 0

    async def run(self, trend):
        self.calls += 1
        raise AssertionError(
            "VideoPipeline must not run during analyze_trends."
        )


class FakeManager:
    def __init__(self):
        self.providers = ["Fake YouTube", "Fake News"]

    def collect_candidates(self, per_provider_limit=25):
        return [
            {"title": "raw-one"},
            {"title": "raw-two"},
        ]


class FakeEngine:
    def process(self, raw_trends, limit=10):
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
                        "Researchers reported a major "
                        "technology discovery."
                    ),
                    "facts": [
                        "Fact one.",
                        "Fact two.",
                        "Fact three.",
                    ],
                    "sources": [
                        {"source": "Publisher A"},
                        {"source": "Publisher B"},
                        {"source": "Publisher C"},
                    ],
                },
            },
        ]


async def main():
    handler = YoutubeAgentHandler()

    handler.engine = FakeEngine()

    fake_pipeline = FakePipeline()
    handler.pipeline = fake_pipeline

    with patch(
        "backend.services.agent_handlers.youtube."
        "build_trend_manager",
        return_value=FakeManager(),
    ):
        result = await handler._analyze_trends(
            "analysis-only-001"
        )

    assert result["status"] == "success"
    assert result["task"] == "analyze_trends"
    assert result["command_id"] == "analysis-only-001"

    assert result["provider_count"] == 2
    assert result["raw_trend_count"] == 2
    assert result["final_trend_count"] == 2

    assert result["best_trend"]["title"] == (
        "Why researchers discovered "
        "a major new technology"
    )

    assert fake_pipeline.calls == 0

    assert "generated_content" not in result
    assert "production_package" not in result

    print("=" * 70)
    print("ANALYSIS-ONLY ROUTING TEST")
    print()
    print("STATUS:", result["status"])
    print(
        "SELECTED:",
        result["best_trend"]["title"],
    )
    print(
        "PRODUCTION SCORE:",
        result["best_trend"][
            "production_selection"
        ]["production_score"],
    )
    print(
        "PIPELINE CALLS:",
        fake_pipeline.calls,
    )
    print()
    print(
        "PASS: analyze_trends selects and "
        "returns a topic without running "
        "VideoPipeline."
    )


asyncio.run(main())
