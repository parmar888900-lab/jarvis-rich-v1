"""Runtime goal strategy integration tests for YoutubeAgentHandler."""

import asyncio

import backend.services.agent_handlers.youtube as youtube_module
from backend.services.agent_handlers.youtube import (
    YoutubeAgentHandler,
)


class FakeSession:
    pass


class FakeSessionContext:
    def __init__(self, factory):
        self.factory = factory

    async def __aenter__(self):
        self.factory.enter_count += 1
        return FakeSession()

    async def __aexit__(
        self,
        exc_type,
        exc,
        traceback,
    ):
        self.factory.exit_count += 1


class FakeSessionFactory:
    def __init__(self):
        self.enter_count = 0
        self.exit_count = 0

    def __call__(self):
        return FakeSessionContext(self)


class FakeCollector:
    async def collect(
        self,
        session,
        *,
        max_items=50,
    ):
        return {
            "status": "completed",
            "channel_id": "channel-1",
            "collected_video_count": 0,
            "snapshot_count": 0,
        }


class FakeEvidenceService:
    async def build(
        self,
        session,
        channel_id,
    ):
        return {
            "channel_id": channel_id,
            "snapshot_count": 0,
            "unique_video_count": 0,
            "video_count": 0,
            "total_views": 0,
            "confidence": 0.0,
            "strategy_ready": False,
            "videos": [],
        }


class FakeGoalStrategyService:
    def __init__(
        self,
        strategy=None,
        error=None,
    ):
        self.strategy = strategy
        self.error = error
        self.calls = 0

    async def build(
        self,
        session,
        *,
        now=None,
    ):
        self.calls += 1

        if self.error is not None:
            raise self.error

        return self.strategy


class FakeManager:
    def __init__(self):
        self.providers = [
            object(),
        ]

    def collect_candidates(
        self,
        *,
        per_provider_limit,
    ):
        assert per_provider_limit == 25

        return [
            {
                "title": (
                    "AI tools are changing "
                    "how videos are made"
                ),
                "source": "Test",
                "final_score": 100.0,
                "category": "Technology",
                "knowledge": {
                    "score": 90.0,
                    "category": "Technology",
                    "summary": (
                        "Useful researched explanation."
                    ),
                    "facts": [
                        "Relevant fact one.",
                        "Relevant fact two.",
                        "Relevant fact three.",
                    ],
                    "sources": [
                        {"source": "Source A"},
                        {"source": "Source B"},
                        {"source": "Source C"},
                    ],
                },
            }
        ]


class FakeEngine:
    def process(
        self,
        raw_trends,
        *,
        limit,
    ):
        assert limit == 10
        return raw_trends


def active_views_strategy():
    return {
        "status": "goal_guided",
        "active_goal_count": 1,
        "primary_goal": {
            "name": "Weekly Views",
            "metric": "views",
        },
        "target_metric": "views",
        "trajectory": "behind",
        "urgency": 1.0,
        "production_priority": 100.0,
        "exploration_bias": 0.0,
        "exploitation_bias": 1.0,
        "scheduler_interval_multiplier": 1.0,
        "rationale": "Test goal strategy.",
    }


def neutral_strategy():
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
        "rationale": "No active production goal.",
    }


async def run_case(
    goal_service,
):
    session_factory = FakeSessionFactory()

    handler = YoutubeAgentHandler(
        performance_collector=FakeCollector(),
        performance_evidence_service=(
            FakeEvidenceService()
        ),
        goal_strategy_service=goal_service,
        session_factory=session_factory,
    )

    handler.engine = FakeEngine()

    original_builder = (
        youtube_module.build_trend_manager
    )

    youtube_module.build_trend_manager = (
        lambda: FakeManager()
    )

    try:
        result = await handler.execute(
            "analyze_trends",
            "goal-runtime-test",
        )
    finally:
        youtube_module.build_trend_manager = (
            original_builder
        )

    return (
        result,
        session_factory,
    )


async def main():
    # -----------------------------------------------------
    # Active views goal reaches the real selector.
    # -----------------------------------------------------

    goal_service = FakeGoalStrategyService(
        strategy=active_views_strategy()
    )

    result, sessions = await run_case(
        goal_service
    )

    assert result["status"] == "success"

    goal_status = result["goal_strategy"]

    assert goal_status["status"] == "success"
    assert goal_status["goal_guided"] is True
    assert (
        goal_status["strategy_status"]
        == "goal_guided"
    )
    assert goal_status["target_metric"] == "views"
    assert (
        goal_status[
            "scheduler_interval_multiplier"
        ]
        == 1.0
    )

    selection = result[
        "best_trend"
    ]["production_selection"]

    assert selection["goal_adjustment"] == 5.0
    assert (
        selection["goal_evidence"]["status"]
        == "applied"
    )

    assert goal_service.calls == 1

    # Analytics and goal strategy deliberately use
    # separate session contexts.
    assert sessions.enter_count == 2
    assert sessions.exit_count == 2

    print(
        "PASS: active runtime goal reaches "
        "real production selection."
    )


    # -----------------------------------------------------
    # No active goal preserves neutral scoring.
    # -----------------------------------------------------

    goal_service = FakeGoalStrategyService(
        strategy=neutral_strategy()
    )

    result, sessions = await run_case(
        goal_service
    )

    assert result["status"] == "success"

    assert (
        result["goal_strategy"][
            "goal_guided"
        ]
        is False
    )

    selection = result[
        "best_trend"
    ]["production_selection"]

    assert selection["goal_adjustment"] == 0.0
    assert (
        selection["goal_evidence"]["status"]
        == "neutral"
    )

    assert sessions.enter_count == 2
    assert sessions.exit_count == 2

    print(
        "PASS: neutral runtime goal preserves "
        "existing selection behavior."
    )


    # -----------------------------------------------------
    # Goal service failure must fail neutral.
    # -----------------------------------------------------

    goal_service = FakeGoalStrategyService(
        error=RuntimeError(
            "simulated goal database failure"
        )
    )

    result, sessions = await run_case(
        goal_service
    )

    assert result["status"] == "success"

    goal_status = result["goal_strategy"]

    assert goal_status["status"] == "unavailable"
    assert goal_status["goal_guided"] is False
    assert goal_status["error_type"] == "RuntimeError"
    assert (
        goal_status[
            "scheduler_interval_multiplier"
        ]
        == 1.0
    )

    selection = result[
        "best_trend"
    ]["production_selection"]

    assert selection["goal_adjustment"] == 0.0
    assert (
        selection["goal_evidence"]["status"]
        == "neutral"
    )

    assert goal_service.calls == 1

    assert sessions.enter_count == 2
    assert sessions.exit_count == 2

    print(
        "PASS: goal strategy failure fails neutral "
        "without blocking production."
    )


    print(
        "PASS: YouTube runtime goal integration "
        "regression suite complete."
    )


asyncio.run(main())
