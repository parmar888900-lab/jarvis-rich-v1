"""Runtime analytics feedback integration for YoutubeAgentHandler."""

import asyncio
from contextlib import asynccontextmanager

from backend.services.agent_handlers.youtube import (
    YoutubeAgentHandler,
)


class FakeSession:
    pass


class FakeSessionFactory:
    def __init__(self):
        self.open_count = 0

    def __call__(self):
        @asynccontextmanager
        async def context():
            self.open_count += 1
            yield FakeSession()

        return context()


class FakeCollector:
    def __init__(
        self,
        *,
        fail=False,
    ):
        self.fail = fail
        self.calls = 0

    async def collect(
        self,
        session,
        *,
        max_items=50,
    ):
        self.calls += 1

        if self.fail:
            raise RuntimeError(
                "simulated analytics provider failure"
            )

        assert isinstance(
            session,
            FakeSession,
        )

        assert max_items == 50

        return {
            "status": "completed",
            "channel_id": "channel-test",
            "collected_video_count": 2,
            "snapshot_count": 2,
            "video_ids": [
                "video-a",
                "video-b",
            ],
        }


class FakeGoalStrategyService:
    """Neutral goal dependency for analytics-only tests."""

    async def build(
        self,
        session,
        *,
        now=None,
    ):
        return {
            "status": "neutral",
            "active_goal_count": 0,
            "primary_goal": None,
            "target_metric": None,
            "trajectory": None,
            "urgency": 0.0,
            "production_priority": 50.0,
            "exploration_bias": 0.5,
            "exploitation_bias": 0.5,
            "scheduler_interval_multiplier": 1.0,
            "rationale": (
                "Analytics regression uses neutral "
                "goal strategy."
            ),
        }


class FakeEvidenceService:
    def __init__(
        self,
        evidence,
    ):
        self.evidence = evidence
        self.calls = 0

    async def build(
        self,
        session,
        channel_id,
    ):
        self.calls += 1

        assert isinstance(
            session,
            FakeSession,
        )

        assert (
            channel_id
            == "channel-test"
        )

        return self.evidence


class FakeManager:
    providers = [
        object(),
        object(),
    ]

    def collect_candidates(
        self,
        *,
        per_provider_limit,
    ):
        assert (
            per_provider_limit
            == 25
        )

        return [
            {
                "title": (
                    "Customer returned shoes after "
                    "wearing them for two years"
                )
            }
        ]


def candidate():
    return {
        "title": (
            "Customer returned shoes after "
            "wearing them for two years"
        ),
        "source": "Test",
        "final_score": 80.0,
        "category": "Stories",
        "knowledge": {
            "score": 85.0,
            "category": "Stories",
            "summary": (
                "Useful researched explanation."
            ),
            "facts": [
                "Relevant fact one.",
                "Relevant fact two.",
                "Relevant fact three.",
            ],
            "sources": [
                {"source": "A"},
                {"source": "B"},
            ],
        },
    }


class FakeEngine:
    def process(
        self,
        raw_trends,
        *,
        limit,
    ):
        assert raw_trends
        assert limit == 10

        return [
            candidate()
        ]


async def run_success_case():
    evidence = {
        "channel_id": "channel-test",
        "snapshot_count": 2,
        "unique_video_count": 2,
        "video_count": 2,
        "source_video_count": 2,
        "excluded_video_count": 0,
        "total_views": 130,
        "sample_confidence": 0.1,
        "audience_confidence": 1.0,
        "confidence": 0.1,
        "strategy_ready": True,
        "baseline_views_per_hour": 1.0,
        "baseline_engagement_rate": 0.01,
        "videos": [
            {
                "video_id": "video-a",
                "title": (
                    "Customer returned shoes after "
                    "wearing them for years"
                ),
                "performance_score": 100.0,
            },
            {
                "video_id": "video-b",
                "title": "Unrelated technology story",
                "performance_score": 50.0,
            },
        ],
    }

    collector = FakeCollector()

    evidence_service = (
        FakeEvidenceService(
            evidence
        )
    )

    session_factory = (
        FakeSessionFactory()
    )

    handler = YoutubeAgentHandler(
        performance_collector=collector,
        performance_evidence_service=(
            evidence_service
        ),
        goal_strategy_service=FakeGoalStrategyService(),
        session_factory=session_factory,
    )

    handler.engine = FakeEngine()

    import backend.services.agent_handlers.youtube as youtube_module

    original_builder = (
        youtube_module.build_trend_manager
    )

    youtube_module.build_trend_manager = (
        lambda: FakeManager()
    )

    try:
        result = await handler._analyze_trends(
            "command-success"
        )
    finally:
        youtube_module.build_trend_manager = (
            original_builder
        )

    assert result["status"] == "success"

    assert (
        result["analytics"]["status"]
        == "success"
    )

    assert (
        result["analytics"][
            "strategy_ready"
        ]
        is True
    )

    assert (
        result["analytics"]["confidence"]
        == 0.1
    )

    decision = result[
        "best_trend"
    ]["production_selection"]

    assert (
        decision["historical_adjustment"]
        > 0.0
    )

    assert (
        decision["production_score"]
        > decision[
            "base_production_score"
        ]
    )

    assert collector.calls == 1
    assert evidence_service.calls == 1
    assert session_factory.open_count == 2

    print(
        "PASS: runtime analytics evidence "
        "reaches production selection."
    )

    print(
        "PASS: strategy-ready relevant history "
        "changes the production score."
    )


async def run_not_ready_case():
    evidence = {
        "channel_id": "channel-test",
        "snapshot_count": 10,
        "unique_video_count": 10,
        "video_count": 9,
        "source_video_count": 10,
        "excluded_video_count": 1,
        "total_views": 10,
        "sample_confidence": 0.45,
        "audience_confidence": 0.1,
        "confidence": 0.045,
        "strategy_ready": False,
        "baseline_views_per_hour": 0.001,
        "baseline_engagement_rate": 0.0,
        "videos": [],
    }

    handler = YoutubeAgentHandler(
        performance_collector=FakeCollector(),
        performance_evidence_service=(
            FakeEvidenceService(
                evidence
            )
        ),
        goal_strategy_service=FakeGoalStrategyService(),
        session_factory=FakeSessionFactory(),
    )

    handler.engine = FakeEngine()

    import backend.services.agent_handlers.youtube as youtube_module

    original_builder = (
        youtube_module.build_trend_manager
    )

    youtube_module.build_trend_manager = (
        lambda: FakeManager()
    )

    try:
        result = await handler._analyze_trends(
            "command-not-ready"
        )
    finally:
        youtube_module.build_trend_manager = (
            original_builder
        )

    assert result["status"] == "success"

    assert (
        result["analytics"][
            "strategy_ready"
        ]
        is False
    )

    assert (
        result["analytics"]["confidence"]
        == 0.045
    )

    decision = result[
        "best_trend"
    ]["production_selection"]

    assert (
        decision["historical_adjustment"]
        == 0.0
    )

    assert (
        decision["production_score"]
        == decision[
            "base_production_score"
        ]
    )

    print(
        "PASS: non-ready channel evidence "
        "remains exactly neutral."
    )


async def run_failure_case():
    collector = FakeCollector(
        fail=True
    )

    evidence_service = (
        FakeEvidenceService(
            {}
        )
    )

    handler = YoutubeAgentHandler(
        performance_collector=collector,
        performance_evidence_service=(
            evidence_service
        ),
        goal_strategy_service=FakeGoalStrategyService(),
        session_factory=FakeSessionFactory(),
    )

    handler.engine = FakeEngine()

    import backend.services.agent_handlers.youtube as youtube_module

    original_builder = (
        youtube_module.build_trend_manager
    )

    youtube_module.build_trend_manager = (
        lambda: FakeManager()
    )

    try:
        result = await handler._analyze_trends(
            "command-failure"
        )
    finally:
        youtube_module.build_trend_manager = (
            original_builder
        )

    assert result["status"] == "success"

    assert (
        result["analytics"]["status"]
        == "unavailable"
    )

    assert (
        result["analytics"][
            "strategy_ready"
        ]
        is False
    )

    assert (
        result["analytics"]["confidence"]
        == 0.0
    )

    assert (
        result["analytics"]["error_type"]
        == "RuntimeError"
    )

    assert evidence_service.calls == 0

    decision = result[
        "best_trend"
    ]["production_selection"]

    assert (
        decision["historical_adjustment"]
        == 0.0
    )

    assert (
        decision["production_score"]
        == decision[
            "base_production_score"
        ]
    )

    print(
        "PASS: analytics provider failure "
        "does not block trend selection."
    )

    print(
        "PASS: analytics failure produces "
        "neutral historical influence."
    )


async def main():
    print("=" * 72)
    print(
        "YOUTUBE RUNTIME ANALYTICS "
        "FEEDBACK TEST"
    )
    print("=" * 72)

    await run_success_case()
    await run_not_ready_case()
    await run_failure_case()

    print("=" * 72)
    print(
        "ALL YOUTUBE RUNTIME ANALYTICS "
        "FEEDBACK TESTS PASSED"
    )
    print("=" * 72)


asyncio.run(main())
