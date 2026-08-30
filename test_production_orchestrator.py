import asyncio

from backend.services.orchestration.production_orchestrator import (
    ProductionOrchestrator,
)


class FakeSession:
    async def __aenter__(self):
        return self

    async def __aexit__(
        self,
        exc_type,
        exc,
        traceback,
    ):
        return False


class FakeSessionFactory:
    def __call__(self):
        return FakeSession()


class FakeCycleService:
    def __init__(self):
        self.calls = []

    async def start_cycle(
        self,
        session,
        *,
        cycle_id,
    ):
        self.calls.append(
            {
                "method": "start_cycle",
                "cycle_id": cycle_id,
            }
        )

    async def complete_cycle(
        self,
        session,
        cycle_id,
        *,
        selected_topic,
        production_score,
        result,
    ):
        self.calls.append(
            {
                "method": "complete_cycle",
                "cycle_id": cycle_id,
                "selected_topic": selected_topic,
                "production_score": production_score,
                "result": result,
            }
        )

    async def mark_no_action(
        self,
        session,
        cycle_id,
        *,
        result,
    ):
        self.calls.append(
            {
                "method": "mark_no_action",
                "cycle_id": cycle_id,
                "result": result,
            }
        )

    async def fail_cycle(
        self,
        session,
        cycle_id,
        *,
        result,
    ):
        self.calls.append(
            {
                "method": "fail_cycle",
                "cycle_id": cycle_id,
                "result": result,
            }
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


def build_orchestrator(
    commander,
    cycle_service,
):
    return ProductionOrchestrator(
        commander=commander,
        cycle_service=cycle_service,
        session_factory=FakeSessionFactory(),
    )


async def test_success():
    commander = FakeCommander()
    cycle_service = FakeCycleService()

    orchestrator = build_orchestrator(
        commander,
        cycle_service,
    )

    result = await orchestrator.run_cycle(
        "cycle-test-001"
    )

    assert result["status"] == "success"
    assert len(commander.calls) == 2

    assert [
        call["method"]
        for call in cycle_service.calls
    ] == [
        "start_cycle",
        "complete_cycle",
    ]

    completion = cycle_service.calls[1]

    assert (
        completion["selected_topic"]
        == "Why researchers discovered "
        "a major new technology"
    )

    assert (
        completion["production_score"]
        == 85.15
    )

    assert (
        completion["result"]
        == result
    )

    produce_call = commander.calls[1]

    assert (
        produce_call["parameters"]["trend"]
        == result["selected_trend"]
    )

    print("=" * 70)
    print("SUCCESS -> COMPLETED TEST")
    print()
    print("STATUS:", result["status"])
    print(
        "PERSISTENCE:",
        [
            call["method"]
            for call in cycle_service.calls
        ],
    )
    print()
    print(
        "PASS: successful production is "
        "persisted as COMPLETED."
    )


async def test_no_action_analysis():
    class NoActionCommander:
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

    commander = NoActionCommander()
    cycle_service = FakeCycleService()

    orchestrator = build_orchestrator(
        commander,
        cycle_service,
    )

    result = await orchestrator.run_cycle(
        "cycle-test-002"
    )

    assert result["status"] == "no_action"
    assert (
        result["reason"]
        == "no_production_ready_topic"
    )
    assert commander.calls == 1

    assert [
        call["method"]
        for call in cycle_service.calls
    ] == [
        "start_cycle",
        "mark_no_action",
    ]

    print()
    print("=" * 70)
    print("NO ACTION ANALYSIS TEST")
    print()
    print("STATUS:", result["status"])
    print("REASON:", result["reason"])
    print()
    print(
        "PASS: lack of a production-ready "
        "topic is persisted as NO_ACTION."
    )


async def test_missing_trend():
    class MissingTrendCommander:
        async def route(
            self,
            agent,
            task,
            command_id,
            parameters=None,
        ):
            return {
                "status": "success",
            }

    cycle_service = FakeCycleService()

    orchestrator = build_orchestrator(
        MissingTrendCommander(),
        cycle_service,
    )

    result = await orchestrator.run_cycle(
        "cycle-test-003"
    )

    assert (
        result["status"]
        == "no_selected_trend"
    )

    assert [
        call["method"]
        for call in cycle_service.calls
    ] == [
        "start_cycle",
        "mark_no_action",
    ]

    print()
    print("=" * 70)
    print("MISSING TREND TEST")
    print()
    print("STATUS:", result["status"])
    print()
    print(
        "PASS: missing selected trend is "
        "persisted as NO_ACTION."
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
    cycle_service = FakeCycleService()

    orchestrator = build_orchestrator(
        commander,
        cycle_service,
    )

    result = await orchestrator.run_cycle(
        "cycle-test-004"
    )

    assert (
        result["status"]
        == "trend_not_authorized"
    )

    assert commander.calls == [
        "analyze_trends"
    ]

    assert [
        call["method"]
        for call in cycle_service.calls
    ] == [
        "start_cycle",
        "mark_no_action",
    ]

    print()
    print("=" * 70)
    print("AUTHORIZATION GATE TEST")
    print()
    print("STATUS:", result["status"])
    print()
    print(
        "PASS: unauthorized trend is "
        "persisted as NO_ACTION."
    )


async def test_analysis_failure():
    class AnalysisFailureCommander:
        async def route(
            self,
            agent,
            task,
            command_id,
            parameters=None,
        ):
            return {
                "status": "provider_failure",
            }

    cycle_service = FakeCycleService()

    orchestrator = build_orchestrator(
        AnalysisFailureCommander(),
        cycle_service,
    )

    result = await orchestrator.run_cycle(
        "cycle-test-005"
    )

    assert (
        result["status"]
        == "analysis_failed"
    )

    assert [
        call["method"]
        for call in cycle_service.calls
    ] == [
        "start_cycle",
        "fail_cycle",
    ]

    print()
    print("=" * 70)
    print("ANALYSIS FAILURE TEST")
    print()
    print("STATUS:", result["status"])
    print()
    print(
        "PASS: genuine analysis failure is "
        "persisted as FAILED."
    )


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
            self.calls.append(task)

            if task == "analyze_trends":
                return {
                    "status": "success",
                    "best_trend": {
                        "title": "Production failure topic",
                        "production_selection": {
                            "eligible": True,
                            "selected": True,
                            "production_score": 81.0,
                        },
                    },
                }

            if task == "create_video":
                return {
                    "status": "production_error",
                    "error": "Fake failure",
                }

            raise AssertionError(
                f"Unexpected task: {task}"
            )

    commander = ProductionFailureCommander()
    cycle_service = FakeCycleService()

    orchestrator = build_orchestrator(
        commander,
        cycle_service,
    )

    result = await orchestrator.run_cycle(
        "cycle-test-006"
    )

    assert (
        result["status"]
        == "production_failed"
    )

    assert commander.calls == [
        "analyze_trends",
        "create_video",
    ]

    assert [
        call["method"]
        for call in cycle_service.calls
    ] == [
        "start_cycle",
        "fail_cycle",
    ]

    print()
    print("=" * 70)
    print("PRODUCTION FAILURE TEST")
    print()
    print("STATUS:", result["status"])
    print()
    print(
        "PASS: production failure is "
        "persisted as FAILED."
    )


async def test_unexpected_exception():
    class ExplodingCommander:
        async def route(
            self,
            agent,
            task,
            command_id,
            parameters=None,
        ):
            raise RuntimeError(
                "Unexpected fake crash"
            )

    cycle_service = FakeCycleService()

    orchestrator = build_orchestrator(
        ExplodingCommander(),
        cycle_service,
    )

    try:
        await orchestrator.run_cycle(
            "cycle-test-007"
        )
    except RuntimeError as exc:
        assert (
            str(exc)
            == "Unexpected fake crash"
        )
    else:
        raise AssertionError(
            "Unexpected exception was swallowed."
        )

    assert [
        call["method"]
        for call in cycle_service.calls
    ] == [
        "start_cycle",
        "fail_cycle",
    ]

    failure = cycle_service.calls[1]

    assert (
        failure["result"]["status"]
        == "orchestration_failed"
    )

    print()
    print("=" * 70)
    print("UNEXPECTED EXCEPTION TEST")
    print()
    print(
        "PERSISTENCE:",
        [
            call["method"]
            for call in cycle_service.calls
        ],
    )
    print()
    print(
        "PASS: unexpected exceptions are "
        "persisted as FAILED and re-raised."
    )


async def main():
    await test_success()
    await test_no_action_analysis()
    await test_missing_trend()
    await test_unauthorized_trend()
    await test_analysis_failure()
    await test_production_failure()
    await test_unexpected_exception()


if __name__ == "__main__":
    asyncio.run(main())
