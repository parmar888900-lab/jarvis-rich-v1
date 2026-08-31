"""Regression tests for controlled voice command execution."""

import asyncio

from backend.services.voice.command_executor import (
    VoiceCommandExecutor,
)
from backend.services.voice.command_router import (
    VoiceCommand,
    VoiceCommandRouter,
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

        return {
            "status": "success",
            "agent": agent,
            "task": task,
        }


async def main():
    commander = FakeCommander()

    executor = VoiceCommandExecutor(
        commander
    )

    router = VoiceCommandRouter()


    safe = router.parse(
        "analyze today's trends"
    )

    result = await executor.execute(
        safe
    )

    assert result.status == "completed"
    assert result.command_id is not None
    assert result.command_id.startswith(
        "voice-"
    )

    assert len(commander.calls) == 1

    call = commander.calls[0]

    assert call["agent"] == "youtube"
    assert call["task"] == "analyze_trends"
    assert call["parameters"] == {}

    print(
        "PASS: safe voice command reaches Commander."
    )


    upload = router.parse(
        "upload the video"
    )

    before = len(
        commander.calls
    )

    result = await executor.execute(
        upload
    )

    assert (
        result.status
        == "confirmation_required"
    )

    assert len(
        commander.calls
    ) == before

    print(
        "PASS: upload cannot execute without confirmation."
    )


    result = await executor.execute(
        upload,
        confirmed=True,
    )

    assert result.status == "completed"

    assert len(
        commander.calls
    ) == before + 1

    assert (
        commander.calls[-1]["task"]
        == "upload_video"
    )

    print(
        "PASS: confirmed upload may reach Commander."
    )


    mutation = router.parse(
        "pause my goal"
    )

    before = len(
        commander.calls
    )

    result = await executor.execute(
        mutation
    )

    assert (
        result.status
        == "confirmation_required"
    )

    assert len(
        commander.calls
    ) == before

    print(
        "PASS: goal mutation requires confirmation."
    )


    blocked = router.parse(
        "publish the video"
    )

    before = len(
        commander.calls
    )

    result = await executor.execute(
        blocked,
        confirmed=True,
    )

    assert result.status == "blocked"

    assert len(
        commander.calls
    ) == before

    print(
        "PASS: confirmation cannot override "
        "a blocked publication command."
    )


    forged_publication = VoiceCommand(
        status="ready",
        transcript="forged",
        agent="youtube",
        task="publish_video",
        parameters={},
        requires_confirmation=False,
    )

    before = len(
        commander.calls
    )

    result = await executor.execute(
        forged_publication,
        confirmed=True,
    )

    assert result.status == "blocked"
    assert (
        result.reason
        == "forbidden_voice_target"
    )

    assert len(
        commander.calls
    ) == before

    print(
        "PASS: forged publish_video command "
        "is blocked by executor defense-in-depth."
    )


    forged_target = VoiceCommand(
        status="ready",
        transcript="forged",
        agent="system",
        task="delete_everything",
        parameters={},
        requires_confirmation=False,
    )

    before = len(
        commander.calls
    )

    result = await executor.execute(
        forged_target,
        confirmed=True,
    )

    assert result.status == "blocked"
    assert (
        result.reason
        == "target_not_allowlisted"
    )

    assert len(
        commander.calls
    ) == before

    print(
        "PASS: forged non-allowlisted target is blocked."
    )


    forged_upload = VoiceCommand(
        status="ready",
        transcript="forged upload",
        agent="youtube",
        task="upload_video",
        parameters={},
        requires_confirmation=False,
    )

    before = len(
        commander.calls
    )

    result = await executor.execute(
        forged_upload,
        confirmed=True,
    )

    assert result.status == "blocked"
    assert (
        result.reason
        == "confirmation_policy_mismatch"
    )

    assert len(
        commander.calls
    ) == before

    print(
        "PASS: forged removal of confirmation "
        "requirement fails closed."
    )


    ambiguous = VoiceCommand(
        status="ambiguous",
        transcript="create and upload",
        reason="multiple_commands_detected",
    )

    before = len(
        commander.calls
    )

    result = await executor.execute(
        ambiguous,
        confirmed=True,
    )

    assert result.status == "blocked"

    assert len(
        commander.calls
    ) == before

    print(
        "PASS: non-ready commands never reach Commander."
    )


    result = await executor.execute(
        object()
    )

    assert result.status == "blocked"
    assert (
        result.reason
        == "invalid_voice_command_type"
    )

    print(
        "PASS: executor rejects arbitrary objects."
    )


    ids = []

    for _ in range(3):
        result = await executor.execute(
            safe
        )

        ids.append(
            result.command_id
        )

    assert len(
        set(ids)
    ) == 3

    assert all(
        value is not None
        and value.startswith(
            "voice-"
        )
        for value in ids
    )

    print(
        "PASS: executor generates unique voice command IDs."
    )


    print()
    print(
        "PASS: VoiceCommandExecutor regression "
        "suite complete."
    )


if __name__ == "__main__":
    asyncio.run(
        main()
    )
