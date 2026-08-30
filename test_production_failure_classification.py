"""Tests for orchestrator structured failure classification."""

import asyncio

from backend.services.orchestration.production_orchestrator import (
    ProductionOrchestrator,
)


def production_ready_analysis():
    return {
        "status": "success",
        "best_trend": {
            "title": "Test Trend",
            "production_selection": {
                "eligible": True,
                "selected": True,
                "production_score": 90,
            },
        },
    }


class FakeCommander:
    def __init__(
        self,
        *,
        analysis,
        production=None,
    ):
        self.analysis = analysis
        self.production = production
        self.calls = []

    async def route(
        self,
        *,
        agent,
        task,
        command_id,
        parameters=None,
    ):
        self.calls.append(task)

        if task == "analyze_trends":
            return self.analysis

        if task == "create_video":
            return self.production

        raise AssertionError(
            f"Unexpected task: {task}"
        )


async def test_transient_analysis_failure():
    commander = FakeCommander(
        analysis={
            "status": "failed",
            "failure_category": (
                "transient_provider_error"
            ),
            "error": "provider timed out",
        }
    )

    orchestrator = ProductionOrchestrator(
        commander=commander
    )

    result = await orchestrator.run_cycle(
        "analysis-transient"
    )

    assert result["status"] == "analysis_failed"

    failure = result["failure"]

    assert (
        failure["category"]
        == "transient_provider_error"
    )
    assert failure["retryable"] is True
    assert (
        failure["detail"]
        == "provider timed out"
    )

    assert commander.calls == [
        "analyze_trends"
    ]

    print(
        "PASS: transient analysis failure "
        "is classified as retryable."
    )


async def test_unknown_analysis_failure():
    commander = FakeCommander(
        analysis={
            "status": "failed",
            "error": "unclassified failure",
        }
    )

    orchestrator = ProductionOrchestrator(
        commander=commander
    )

    result = await orchestrator.run_cycle(
        "analysis-unknown"
    )

    failure = result["failure"]

    assert failure["category"] == "unknown"
    assert failure["retryable"] is False

    print(
        "PASS: unknown analysis failure "
        "fails closed."
    )


async def test_rate_limited_production():
    commander = FakeCommander(
        analysis=production_ready_analysis(),
        production={
            "status": "failed",
            "failure_category": "rate_limited",
            "error": "provider rate limit",
        },
    )

    orchestrator = ProductionOrchestrator(
        commander=commander
    )

    result = await orchestrator.run_cycle(
        "production-rate-limit"
    )

    assert result["status"] == "production_failed"

    failure = result["failure"]

    assert failure["category"] == "rate_limited"
    assert failure["retryable"] is True

    assert commander.calls == [
        "analyze_trends",
        "create_video",
    ]

    print(
        "PASS: production rate limit "
        "is classified as retryable."
    )


async def test_validation_failure():
    commander = FakeCommander(
        analysis=production_ready_analysis(),
        production={
            "status": "failed",
            "failure_category": (
                "validation_error"
            ),
            "error": "content rejected",
        },
    )

    orchestrator = ProductionOrchestrator(
        commander=commander
    )

    result = await orchestrator.run_cycle(
        "production-validation"
    )

    failure = result["failure"]

    assert (
        failure["category"]
        == "validation_error"
    )
    assert failure["retryable"] is False

    print(
        "PASS: validation failure "
        "is classified as permanent."
    )


async def main():
    print("=" * 70)
    print(
        "ORCHESTRATOR FAILURE "
        "CLASSIFICATION TEST"
    )
    print()

    await test_transient_analysis_failure()
    await test_unknown_analysis_failure()
    await test_rate_limited_production()
    await test_validation_failure()

    print()
    print("=" * 70)
    print(
        "ALL ORCHESTRATOR FAILURE "
        "CLASSIFICATION TESTS PASSED"
    )


if __name__ == "__main__":
    asyncio.run(main())
