"""Integration test for the autonomous YouTube production path.

Exercises the real:
    ProductionRunner
    ProductionOrchestrator
    Commander
    AgentRegistry
    YoutubeAgentHandler

External and expensive provider boundaries are replaced with fakes.
No real generation or YouTube publishing occurs.
"""

import asyncio
import hashlib
import tempfile
from pathlib import Path

import backend.services.agent_handlers.youtube as youtube_module

from backend.services.agent_registry import (
    build_default_registry,
)
from backend.services.commander import Commander
from backend.services.orchestration.idempotency import (
    OperationType,
)
from backend.services.orchestration.production_orchestrator import (
    ProductionOrchestrator,
)
from backend.services.orchestration.production_runner import (
    ProductionRunner,
)


class FakeTrendManager:
    def __init__(self):
        self.providers = [
            object(),
            object(),
        ]
        self.calls = []

    def collect_candidates(
        self,
        *,
        per_provider_limit,
    ):
        self.calls.append(
            per_provider_limit
        )

        return [
            {
                "title": (
                    "AI-generated videos are "
                    "becoming more realistic"
                ),
                "source": "fake-provider",
            }
        ]


class FakeTrendEngine:
    def __init__(self):
        self.calls = []

    def process(
        self,
        raw_trends,
        *,
        limit,
    ):
        self.calls.append(
            {
                "raw_trends": raw_trends,
                "limit": limit,
            }
        )

        return [
            {
                "title": (
                    "AI-generated videos are "
                    "becoming more realistic"
                ),
                "source": "fake-provider",
            }
        ]


class FakeSelector:
    def __init__(self):
        self.calls = []

    def select(
        self,
        ranked_trends,
    ):
        self.calls.append(
            ranked_trends
        )

        return {
            "title": (
                "AI-generated videos are "
                "becoming more realistic"
            ),
            "source": "fake-provider",
            "production_selection": {
                "eligible": True,
                "selected": True,
                "production_score": 94.0,
            },
        }


class FakeGeneratedContent:
    def to_dict(self):
        return {
            "title": (
                "Why AI Videos Are "
                "Getting So Realistic"
            ),
            "script": (
                "Synthetic integration "
                "test content."
            ),
            "hashtags": [
                "AI",
                "technology",
                "shorts",
            ],
        }


class FakeVideoPipeline:
    def __init__(
        self,
        video_path,
    ):
        self.video_path = str(
            video_path
        )
        self.calls = []

    async def run(
        self,
        trend,
    ):
        self.calls.append(
            trend
        )

        return {
            "generated": (
                FakeGeneratedContent()
            ),
            "content_validation": {
                "status": "accepted",
            },
            "storyboard": {
                "status": "success",
            },
            "images": [],
            "production_package": {
                "package_dir": (
                    "generated/fake-package"
                ),
            },
            "video": {
                "status": "success",
                "video_path": (
                    self.video_path
                ),
                "duration": 42.0,
                "resolution": "1080x1920",
                "fps": 30,
            },
            "status": "success",
        }


class FakePublisher:
    def __init__(self):
        self.channel_calls = 0
        self.upload_calls = []

    def get_authorized_channel(self):
        self.channel_calls += 1

        return {
            "status": "authorized",
            "channel_id": (
                "integration-test-channel"
            ),
            "channel_title": (
                "Integration Test Channel"
            ),
        }

    async def upload_video(
        self,
        *,
        video_path,
        title,
        description,
        tags,
        privacy_status,
        category_id,
        operation_tag=None,
    ):
        call = {
            "video_path": str(
                video_path
            ),
            "title": title,
            "description": description,
            "tags": list(
                tags
            ),
            "privacy_status": (
                privacy_status
            ),
            "category_id": (
                category_id
            ),
        }

        self.upload_calls.append(
            call
        )

        return {
            "status": "uploaded",
            "video_id": (
                "fake-autonomous-video-123"
            ),
            "privacy_status": (
                privacy_status
            ),
            "title": title,
        }


class FakeOperationExecutor:
    def __init__(self):
        self.calls = []

    async def execute(
        self,
        *,
        operation_type,
        resource_id,
        operation,
    ):
        self.calls.append(
            {
                "operation_type": (
                    operation_type
                ),
                "resource_id": (
                    resource_id
                ),
            }
        )

        provider_result = (
            await operation()
        )

        return {
            "status": "completed",
            "executed": True,
            "idempotency_key": (
                "fake-autonomous-"
                "idempotency-key"
            ),
            "result": provider_result,
        }


async def main():
    print("=" * 72)
    print(
        "FULL AUTONOMOUS YOUTUBE "
        "ROUTING INTEGRATION TEST"
    )
    print("=" * 72)
    print()

    temp_path = None

    original_manager_builder = (
        youtube_module
        .build_trend_manager
    )

    try:
        with tempfile.NamedTemporaryFile(
            suffix=".mp4",
            delete=False,
        ) as handle:
            handle.write(
                b"jarvis-autonomous-"
                b"integration-test-video"
            )

            temp_path = Path(
                handle.name
            )

        expected_hash = hashlib.sha256(
            temp_path.read_bytes()
        ).hexdigest()

        # --------------------------------------------------
        # REAL DEFAULT REGISTRY
        # --------------------------------------------------

        registry = (
            build_default_registry()
        )

        youtube_handler = (
            registry.get("youtube")
        )

        print(
            "PASS: real default AgentRegistry "
            "constructed."
        )

        print(
            "PASS: real YoutubeAgentHandler "
            "resolved from registry."
        )

        # --------------------------------------------------
        # REPLACE ONLY EXTERNAL / EXPENSIVE BOUNDARIES
        # --------------------------------------------------

        fake_manager = (
            FakeTrendManager()
        )

        fake_engine = (
            FakeTrendEngine()
        )

        fake_selector = (
            FakeSelector()
        )

        fake_pipeline = (
            FakeVideoPipeline(
                temp_path
            )
        )

        fake_publisher = (
            FakePublisher()
        )

        fake_executor = (
            FakeOperationExecutor()
        )

        youtube_module.build_trend_manager = (
            lambda: fake_manager
        )

        youtube_handler.engine = (
            fake_engine
        )

        youtube_handler.selector = (
            fake_selector
        )

        youtube_handler.pipeline = (
            fake_pipeline
        )

        youtube_handler.publisher = (
            fake_publisher
        )

        youtube_handler.operation_executor = (
            fake_executor
        )

        # --------------------------------------------------
        # REAL COMMANDER
        # --------------------------------------------------

        commander = Commander(
            registry=registry
        )

        # --------------------------------------------------
        # REAL PRODUCTION ORCHESTRATOR
        #
        # Persistence is intentionally omitted here.
        # Existing persistence regressions already cover
        # ProductionCycleService separately.
        # --------------------------------------------------

        orchestrator = (
            ProductionOrchestrator(
                commander=commander
            )
        )

        # --------------------------------------------------
        # REAL PRODUCTION RUNNER
        # --------------------------------------------------

        runner = ProductionRunner(
            orchestrator,
            cycle_id_factory=(
                lambda: (
                    "autonomous-integration-001"
                )
            ),
        )

        result = (
            await runner.run_cycle()
        )

        # --------------------------------------------------
        # ASSERT COMPLETE REAL ROUTING CHAIN
        # --------------------------------------------------

        assert (
            result["cycle_id"]
            == "autonomous-integration-001"
        )

        assert (
            result["status"]
            == "success"
        )

        print(
            "PASS: ProductionRunner completed "
            "through real ProductionOrchestrator."
        )

        assert (
            fake_manager.calls
            == [25]
        )

        assert (
            len(fake_engine.calls)
            == 1
        )

        assert (
            fake_engine.calls[0]["limit"]
            == 10
        )

        assert (
            len(fake_selector.calls)
            == 1
        )

        print(
            "PASS: analyze_trends routed through "
            "the real YouTube handler."
        )

        assert (
            len(fake_pipeline.calls)
            == 1
        )

        produced_trend = (
            fake_pipeline.calls[0]
        )

        assert (
            produced_trend[
                "production_selection"
            ]["eligible"]
            is True
        )

        assert (
            produced_trend[
                "production_selection"
            ]["selected"]
            is True
        )

        print(
            "PASS: selected trend reached the "
            "real create_video handler."
        )

        assert (
            result[
                "production"
            ]["video"]["video_path"]
            == str(temp_path)
        )

        print(
            "PASS: create_video exposed the "
            "rendered artifact contract."
        )

        assert (
            len(fake_executor.calls)
            == 1
        )

        executor_call = (
            fake_executor.calls[0]
        )

        assert (
            executor_call[
                "operation_type"
            ]
            == OperationType.UPLOAD_VIDEO
        )

        expected_resource_id = (
            "youtube:"
            "integration-test-channel:"
            f"{expected_hash}"
        )

        assert (
            executor_call["resource_id"]
            == expected_resource_id
        )

        print(
            "PASS: upload crossed the real "
            "idempotent operation boundary."
        )

        assert (
            fake_publisher.channel_calls
            == 1
        )

        assert (
            len(fake_publisher.upload_calls)
            == 1
        )

        upload_call = (
            fake_publisher.upload_calls[0]
        )

        assert (
            Path(
                upload_call[
                    "video_path"
                ]
            ).resolve()
            == temp_path.resolve()
        )

        assert (
            upload_call["title"]
            == (
                "Why AI Videos Are "
                "Getting So Realistic"
            )
        )

        assert (
            upload_call["tags"]
            == [
                "AI",
                "technology",
                "shorts",
            ]
        )

        assert (
            upload_call[
                "privacy_status"
            ]
            == "private"
        )

        print(
            "PASS: exact rendered MP4 reached "
            "the protected publisher boundary."
        )

        print(
            "PASS: autonomous visibility "
            "remained PRIVATE."
        )

        assert (
            result["upload"]["status"]
            == "completed"
        )

        assert (
            result[
                "upload"
            ]["upload"]["result"]["video_id"]
            == (
                "fake-autonomous-video-123"
            )
        )

        print(
            "PASS: provider completion propagated "
            "back through handler and orchestrator."
        )

        print()
        print("=" * 72)
        print(
            "FULL AUTONOMOUS YOUTUBE "
            "ROUTING INTEGRATION PASSED"
        )
        print("=" * 72)

    finally:
        youtube_module.build_trend_manager = (
            original_manager_builder
        )

        if (
            temp_path is not None
            and temp_path.exists()
        ):
            temp_path.unlink()


if __name__ == "__main__":
    asyncio.run(
        main()
    )
