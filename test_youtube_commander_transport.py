import asyncio

from backend.services.agent_registry import AgentRegistry
from backend.services.commander import Commander


class CaptureYoutubeHandler:
    name = "youtube"

    supported_tasks = frozenset(
        {
            "create_video",
        }
    )

    def supports_task(self, task):
        return task in self.supported_tasks

    async def execute(
        self,
        task,
        command_id,
        **kwargs,
    ):
        return {
            "task": task,
            "command_id": command_id,
            "received_parameters": kwargs,
        }


async def main():
    registry = AgentRegistry()

    handler = CaptureYoutubeHandler()

    registry.register(handler)

    commander = Commander(
        registry=registry
    )

    trend = {
        "title": (
            "Why researchers discovered "
            "a major new technology"
        ),
        "source": "Google News RSS",
        "final_score": 80,
        "knowledge": {
            "score": 90,
            "summary": "Research summary.",
            "facts": [
                "Fact one.",
                "Fact two.",
            ],
            "sources": [
                {
                    "source": "Publisher A",
                    "url": "https://example.com/a",
                },
                {
                    "source": "Publisher B",
                    "url": "https://example.com/b",
                },
            ],
        },
        "production_selection": {
            "eligible": True,
            "selected": True,
            "production_score": 85.15,
        },
    }

    result = await commander.route(
        agent="youtube",
        task="create_video",
        command_id="transport-test-001",
        parameters={
            "trend": trend,
        },
    )

    received = result[
        "received_parameters"
    ]

    assert result["task"] == "create_video"

    assert result["command_id"] == (
        "transport-test-001"
    )

    assert "trend" in received

    received_trend = received["trend"]

    assert received_trend == trend

    assert received_trend is trend

    assert (
        received_trend["knowledge"]["score"]
        == 90
    )

    assert (
        received_trend[
            "production_selection"
        ]["production_score"]
        == 85.15
    )

    assert (
        received_trend["knowledge"]["sources"][1]
        ["source"]
        == "Publisher B"
    )

    print("=" * 70)
    print("COMMANDER NESTED PARAMETER TEST")
    print()
    print(
        "TASK:",
        result["task"],
    )
    print(
        "TITLE:",
        received_trend["title"],
    )
    print(
        "RESEARCH CONFIDENCE:",
        received_trend["knowledge"]["score"],
    )
    print(
        "PRODUCTION SCORE:",
        received_trend[
            "production_selection"
        ]["production_score"],
    )
    print()
    print(
        "PASS: Commander preserves the "
        "complete nested trend dictionary."
    )


asyncio.run(main())
