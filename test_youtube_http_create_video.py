import json
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from backend.app import app
from backend.database import Base, get_db
from backend.models import command  # noqa: F401
from backend.routes import commander as commander_route
from backend.services.agent_handlers.youtube import (
    YoutubeAgentHandler,
)
from backend.services.agent_registry import AgentRegistry
from backend.services.commander import Commander


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
    temp_dir = tempfile.TemporaryDirectory()

    db_path = (
        Path(temp_dir.name)
        / "jarvis_http_test.db"
    )

    test_engine = create_async_engine(
        f"sqlite+aiosqlite:///{db_path}",
        echo=False,
    )

    TestSession = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with test_engine.begin() as conn:
        await conn.run_sync(
            Base.metadata.create_all
        )

    async def override_get_db():
        async with TestSession() as session:
            yield session

    youtube = YoutubeAgentHandler()

    fake_pipeline = FakePipeline()
    youtube.pipeline = fake_pipeline

    registry = AgentRegistry()
    registry.register(youtube)

    test_commander = Commander(
        registry=registry
    )

    original_commander = (
        commander_route.commander
    )

    commander_route.commander = (
        test_commander
    )

    app.dependency_overrides[
        get_db
    ] = override_get_db

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
                    "url": (
                        "https://example.com/a"
                    ),
                },
                {
                    "source": "Publisher B",
                    "url": (
                        "https://example.com/b"
                    ),
                },
            ],
        },
        "production_selection": {
            "eligible": True,
            "selected": True,
            "production_score": 85.15,
        },
    }

    payload = {
        "agent": "youtube",
        "task": "create_video",
        "priority": "normal",
        "parameters": {
            "trend": trend,
        },
    }

    try:
        with TestClient(app) as client:
            response = client.post(
                "/command",
                json=payload,
            )

            assert response.status_code == 200

            body = response.json()

            assert body["status"] == "accepted"

            command_id = body["command_id"]

            status_response = client.get(
                f"/command/{command_id}"
            )

            assert (
                status_response.status_code
                == 200
            )

            record = status_response.json()

        assert record["status"] == "completed"

        stored_result = json.loads(
            record["result"]
        )

        assert (
            stored_result["status"]
            == "success"
        )

        assert (
            stored_result["task"]
            == "create_video"
        )

        assert fake_pipeline.calls == 1

        assert (
            fake_pipeline.received_trend
            == trend
        )

        assert (
            stored_result["trend"]
            == trend
        )

        assert (
            stored_result[
                "generated_content"
            ]["title"]
            == "Generated test short"
        )

        assert (
            stored_result[
                "production_package"
            ]["video_path"]
            == "generated/test.mp4"
        )

        print("=" * 70)
        print("FULL HTTP CREATE_VIDEO TEST")
        print()
        print(
            "POST STATUS:",
            response.status_code,
        )
        print(
            "COMMAND STATUS:",
            record["status"],
        )
        print(
            "AGENT RESULT:",
            stored_result["status"],
        )
        print(
            "PIPELINE CALLS:",
            fake_pipeline.calls,
        )
        print(
            "TITLE:",
            fake_pipeline.received_trend[
                "title"
            ],
        )
        print()
        print(
            "PASS: HTTP -> Commander -> "
            "YouTube Agent -> VideoPipeline "
            "routing works end-to-end."
        )

    finally:
        commander_route.commander = (
            original_commander
        )

        app.dependency_overrides.clear()

        await test_engine.dispose()

        temp_dir.cleanup()


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
