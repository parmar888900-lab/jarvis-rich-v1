import asyncio
from unittest.mock import patch

from backend.services.agent_handlers.youtube import (
    YoutubeAgentHandler,
)


class FakePipeline:
    def __init__(self):
        self.calls = 0

    async def run(self, trend):
        self.calls += 1
        raise AssertionError(
            "Pipeline must not run when no "
            "production-ready topic exists."
        )


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
        return [
            {
                "title": "THIS IS NOT A GAME",
                "source": "YouTube",
                "final_score": 99,
                "category": "General",
                "knowledge": {
                    "score": 5,
                    "summary": "",
                    "facts": [],
                    "sources": [],
                },
            },
            {
                "title": "Official Music Video New Song",
                "source": "YouTube",
                "final_score": 95,
                "category": "General",
                "knowledge": {
                    "score": 80,
                    "summary": (
                        "Researched information."
                    ),
                    "facts": [
                        "Fact one.",
                        "Fact two.",
                        "Fact three.",
                    ],
                    "sources": [
                        {"source": "A"},
                        {"source": "B"},
                        {"source": "C"},
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
            "test-command-reject"
        )

    assert result["status"] == (
        "no_production_ready_topic"
    )

    assert result["command_id"] == (
        "test-command-reject"
    )

    assert result["provider_count"] == 2
    assert result["raw_trend_count"] == 2
    assert result["final_trend_count"] == 2

    assert fake_pipeline.calls == 0

    print("=" * 70)
    print("NO-ELIGIBLE-TOPIC TEST")
    print()
    print("STATUS:", result["status"])
    print(
        "PIPELINE CALLS:",
        fake_pipeline.calls,
    )
    print()
    print(
        "PASS: YouTube agent fails closed "
        "when no production-ready topic exists."
    )


asyncio.run(main())
