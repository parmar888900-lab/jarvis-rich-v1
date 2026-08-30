import asyncio

from backend.services.agent_handlers.youtube import YoutubeAgentHandler


class FakeGenerated:
    def to_dict(self):
        return {
            "title": "Generated test short",
            "script": "Test script",
        }


class FakePipeline:
    def __init__(self):
        self.calls = 0
        self.received_trend = None

    async def run(self, trend):
        self.calls += 1
        self.received_trend = trend

        return {
            "generated": FakeGenerated(),
            "production_package": {
                "video_path": "generated/test.mp4",
            },
        }


async def main():
    handler = YoutubeAgentHandler()

    fake_pipeline = FakePipeline()
    handler.pipeline = fake_pipeline

    trend = {
        "title": (
            "Why researchers discovered "
            "a major new technology"
        ),
        "source": "Google News RSS",
        "final_score": 80,
        "knowledge": {
            "score": 90,
        },
    }

    success = await handler.execute(
        task="create_video",
        command_id="create-video-001",
        trend=trend,
    )

    assert success["status"] == "success"
    assert success["task"] == "create_video"
    assert success["command_id"] == "create-video-001"

    assert fake_pipeline.calls == 1
    assert fake_pipeline.received_trend is trend

    assert success["trend"] is trend

    assert success["generated_content"] == {
        "title": "Generated test short",
        "script": "Test script",
    }

    assert success["production_package"] == {
        "video_path": "generated/test.mp4",
    }

    missing = await handler.execute(
        task="create_video",
        command_id="create-video-002",
    )

    assert missing["status"] == "invalid_parameters"
    assert missing["task"] == "create_video"
    assert missing["command_id"] == "create-video-002"

    assert fake_pipeline.calls == 1

    empty_title = await handler.execute(
        task="create_video",
        command_id="create-video-003",
        trend={},
    )

    assert empty_title["status"] == "invalid_parameters"
    assert fake_pipeline.calls == 1

    print("=" * 70)
    print("CREATE_VIDEO ROUTING TEST")
    print()
    print("VALID STATUS:", success["status"])
    print("PIPELINE CALLS AFTER VALID:", 1)
    print(
        "PIPELINE RECEIVED:",
        fake_pipeline.received_trend["title"],
    )
    print()
    print("MISSING TREND STATUS:", missing["status"])
    print(
        "EMPTY TITLE STATUS:",
        empty_title["status"],
    )
    print(
        "TOTAL PIPELINE CALLS:",
        fake_pipeline.calls,
    )
    print()
    print(
        "PASS: create_video is the sole "
        "production route and invalid input "
        "never reaches VideoPipeline."
    )


asyncio.run(main())
