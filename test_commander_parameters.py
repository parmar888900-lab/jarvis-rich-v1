import asyncio

from backend.services.agent_handlers.base import BaseAgentHandler
from backend.services.agent_registry import AgentRegistry
from backend.services.commander import (
    Commander,
    CommandValidationError,
)
from backend.models.command import CommandSubmitRequest


class TestHandler(BaseAgentHandler):
    name = "test"
    supported_tasks = frozenset(
        {"parameter_test"}
    )

    async def execute(
        self,
        task: str,
        command_id: str,
        **kwargs,
    ) -> dict:
        return {
            "task": task,
            "command_id": command_id,
            "received": kwargs,
        }


async def main():
    registry = AgentRegistry()
    registry.register(TestHandler())

    commander = Commander(
        registry=registry
    )

    result = await commander.route(
        agent="test",
        task="parameter_test",
        command_id="transport-test",
        parameters={
            "target_value": 100000,
            "metric": "views",
            "period": "weekly",
        },
    )

    print("ROUTE RESULT:")
    print(result)

    assert result["received"] == {
        "target_value": 100000,
        "metric": "views",
        "period": "weekly",
    }

    safe = CommandSubmitRequest(
        agent="test",
        task="parameter_test",
        parameters={
            "target_value": 100000,
        },
    )

    commander.validate(safe)

    print()
    print(
        "PASS: structured parameters "
        "reach agent handlers."
    )

    malicious = CommandSubmitRequest(
        agent="test",
        task="parameter_test",
        parameters={
            "command_id": "fake",
        },
    )

    try:
        commander.validate(malicious)
    except CommandValidationError as exc:
        print(
            "RESERVED KEY REJECTED:",
            exc,
        )
    else:
        raise AssertionError(
            "Reserved command_id was accepted."
        )

    print()
    print(
        "PASS: reserved routing keys "
        "are protected."
    )


asyncio.run(main())
