import asyncio

from backend.services.agent_handlers.system import (
    SystemAgentHandler,
)


async def main():
    handler = SystemAgentHandler()

    result = await handler.execute(
        task="get_status",
        command_id="status-test",
    )

    print(result["message"])
    print()
    print("Production:", result["production"])
    print()
    print("YouTube:", result["youtube"])


asyncio.run(main())
