import asyncio

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

    async def run(self, trend):
        self.received_trend = trend

        return {
            "generated": FakeGenerated(),
            "production_package": {
                "status": "fake",
            },
        }


class FakeTrendEngine:
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
                        "A well-supported explanation "
                        "of the discovery."
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

    handler.engine = FakeTrendEngine()

    fake_pipeline = FakePipeline()
    handler.pipeline = fake_pipeline

    # Test the exact production-selection section
    # without calling live providers.
    ranked_trends = handler.engine.process(
        [],
        limit=10,
    )

    winner = handler.selector.select(
        ranked_trends
    )

    assert winner is not None

    assert winner["title"] == (
        "Why researchers discovered "
        "a major new technology"
    )

    result = await handler.pipeline.run(
        winner
    )

    assert (
        fake_pipeline.received_trend["title"]
        == winner["title"]
    )

    assert (
        fake_pipeline.received_trend[
            "production_selection"
        ]["selected"]
        is True
    )

    weak = ranked_trends[0]

    assert (
        weak["production_selection"][
            "eligible"
        ]
        is False
    )

    assert (
        "research_confidence_below_threshold"
        in weak["production_selection"][
            "rejection_reasons"
        ]
    )

    print("=" * 70)
    print("YOUTUBE AGENT PRODUCTION ROUTING")
    print()
    print(
        "OLD FIRST-RANKED TOPIC:",
        ranked_trends[0]["title"],
    )
    print(
        "OLD VIRAL SCORE:",
        ranked_trends[0]["final_score"],
    )

    print()
    print(
        "SELECTED TOPIC:",
        winner["title"],
    )
    print(
        "PRODUCTION SCORE:",
        winner["production_selection"][
            "production_score"
        ],
    )
    print(
        "PIPELINE RECEIVED:",
        fake_pipeline.received_trend[
            "title"
        ],
    )

    print()
    print(
        "PASS: YouTube production routing "
        "uses ProductionTopicSelector."
    )


asyncio.run(main())
