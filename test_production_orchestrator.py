import asyncio

from backend.services.orchestration.production_orchestrator import (
    ProductionOrchestrator,
)


class FakeCommander:
    def __init__(self):
        self.calls = []

    async def route(
        self,
        agent,
        task,
        command_id,
        parameters=None,
    ):
        self.calls.append(
            {
                "agent": agent,
                "task": task,
                "command_id": command_id,
                "parameters": parameters,
            }
        )

        if task == "analyze_trends":
            return {
                "status": "success",
                "best_trend": {
                    "title": (
                        "Why researchers discovered "
                        "a major new technology"
                    ),
                    "knowledge": {
                        "score": 90,
                    },
                    "production_selection": {
                        "eligible": True,
                        "selected": True,
                        "production_score": 85.15,
                    },
                },
            }

        if task == "create_video":
            return {
                "status": "success",
                "generated_content": {
                    "title": "Generated test short",
                },
                "production_package": {
                    "video_path": "generated/test.mp4",
                },
            }

        raise AssertionError(
            f"Unexpected task: {task}"
        )


async def test_success():
    fake_commander = FakeCommander()

    orchestrator = ProductionOrchestrator(
        commander=fake_commander,
    )

    result = await orchestrator.run_cycle(
        "cycle-test-001"
    )

    assert result["status"] == "success"

    assert len(fake_commander.calls) == 2

    analyze_call = fake_commander.calls[0]
    produce_call = fake_commander.calls[1]

    assert analyze_call["agent"] == "youtube"
    assert analyze_call["task"] == "analyze_trends"
    assert (
        analyze_call["command_id"]
        == "cycle-test-001:analyze"
    )
    assert analyze_call["parameters"] is None

    assert produce_call["agent"] == "youtube"
    assert produce_call["task"] == "create_video"
    assert (
        produce_call["command_id"]
        == "cycle-test-001:produce"
    )

    trend = result["selected_trend"]

    assert (
        produce_call["parameters"]["trend"]
        == trend
    )

    assert (
        trend["production_selection"][
            "selected"
        ]
        is True
    )

    print("=" * 70)
    print("PRODUCTION ORCHESTRATOR SUCCESS TEST")
    print()
    print(
        "STATUS:",
        result["status"],
    )
    print(
        "ROUTE CALLS:",
        len(fake_commander.calls),
    )
    print(
        "SELECTED:",
        trend["title"],
    )
    print(
        "PRODUCTION SCORE:",
        trend["production_selection"][
            "production_score"
        ],
    )
    print()
    print(
        "PASS: orchestrator performs "
        "analyze_trends -> create_video "
        "with the exact selected trend."
    )


async def test_analysis_failure():
    class AnalysisFailureCommander:
        def __init__(self):
            self.calls = 0

        async def route(
            self,
            agent,
            task,
            command_id,
            parameters=None,
        ):
            self.calls += 1

            return {
                "status": (
                    "no_production_ready_topic"
                ),
            }

    commander = AnalysisFailureCommander()

    orchestrator = ProductionOrchestrator(
        commander=commander,
    )

    result = await orchestrator.run_cycle(
        "cycle-test-002"
    )

    assert (
        result["status"]
        == "analysis_failed"
    )

    assert commander.calls == 1

    print()
    print("=" * 70)
    print("ANALYSIS FAILURE TEST")
    print()
    print(
        "STATUS:",
        result["status"],
    )
    print(
        "ROUTE CALLS:",
        commander.calls,
    )
    print()
    print(
        "PASS: failed analysis stops "
        "before production."
    )


async def test_unauthorized_trend():
    class UnauthorizedCommander:
        def __init__(self):
            self.calls = []

        async def route(
            self,
            agent,
            task,
            command_id,
            parameters=None,
        ):
            self.calls.append(task)

            if task == "analyze_trends":
                return {
                    "status": "success",
                    "best_trend": {
                        "title": "Weak topic",
                        "production_selection": {
                            "eligible": False,
                            "selected": False,
                        },
                    },
                }

            raise AssertionError(
                "create_video must not run"
            )

    commander = UnauthorizedCommander()

    orchestrator = ProductionOrchestrator(
        commander=commander,
    )

    result = await orchestrator.run_cycle(
        "cycle-test-003"
    )

    assert (
        result["status"]
        == "trend_not_authorized"
    )

    assert commander.calls == [
        "analyze_trends"
    ]

    print()
    print("=" * 70)
    print("AUTHORIZATION GATE TEST")
    print()
    print(
        "STATUS:",
        result["status"],
    )
    print(
        "ROUTE CALLS:",
        commander.calls,
    )
    print()
    print(
        "PASS: non-authorized trends "
        "never reach create_video."
    )


async def main():
    await test_success()
    await test_analysis_failure()
    await test_unauthorized_trend()


asyncio.run(main())

async def test_production_failure():
    class ProductionFailureCommander:
        def __init__(self):
            self.calls = []

        async def route(
            self,
            agent,
            task,
            command_id,
            parameters=None,
        ):
            self.calls.append(
                {
                    "task": task,
                    "parameters": parameters,
                }
            )

            if task == "analyze_trends":
                return {
                    "status": "success",
                    "best_trend": {
                        "title": (
                            "Why researchers discovered "
                            "a major new technology"
                        ),
                        "production_selection": {
                            "eligible": True,
                            "selected": True,
                            "production_score": 85.15,
                        },
                    },
                }

            if task == "create_video":
                return {
                    "status": "production_error",
                    "error": "Fake production failure",
                }

            raise AssertionError(
                f"Unexpected task: {task}"
            )

    commander = ProductionFailureCommander()

    orchestrator = ProductionOrchestrator(
        commander=commander,
    )

    result = await orchestrator.run_cycle(
        "cycle-test-004"
    )

    assert (
        result["status"]
        == "production_failed"
    )

    assert len(commander.calls) == 2

    assert (
        commander.calls[0]["task"]
        == "analyze_trends"
    )

    assert (
        commander.calls[1]["task"]
        == "create_video"
    )

    assert (
        result["production"]["status"]
        == "production_error"
    )

    print()
    print("=" * 70)
    print("PRODUCTION FAILURE TEST")
    print()
    print(
        "STATUS:",
        result["status"],
    )
    print(
        "ROUTE CALLS:",
        len(commander.calls),
    )
    print(
        "PRODUCTION STATUS:",
        result["production"]["status"],
    )
    print()
    print(
        "PASS: production failure is "
        "returned without reporting the "
        "cycle as successful."
    )


asyncio.run(test_production_failure())
