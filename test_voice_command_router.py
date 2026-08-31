"""Regression tests for the Jarvis voice command router."""

from backend.services.voice.command_router import (
    VoiceCommandRouter,
)


def main():
    router = VoiceCommandRouter()


    result = router.parse(
        "analyze today's trends"
    )

    assert result.status == "ready"
    assert result.executable is True
    assert result.agent == "youtube"
    assert result.task == "analyze_trends"
    assert result.requires_confirmation is False

    print(
        "PASS: trend analysis maps to YouTube safely."
    )


    result = router.parse(
        "analyse today's trends"
    )

    assert result.status == "ready"
    assert result.task == "analyze_trends"

    print(
        "PASS: Whisper British spelling variation is supported."
    )


    result = router.parse(
        "create a video"
    )

    assert result.status == "ready"
    assert result.agent == "youtube"
    assert result.task == "create_video"
    assert result.requires_confirmation is False

    print(
        "PASS: video creation is allowlisted."
    )


    result = router.parse(
        "upload the video"
    )

    assert result.status == "ready"
    assert result.task == "upload_video"
    assert result.requires_confirmation is True

    print(
        "PASS: upload requires explicit confirmation."
    )


    for command in (
        "publish the video",
        "make the video public",
        "make it public",
        "set the video to public",
        "change it to public",
        "go public",
    ):
        result = router.parse(
            command
        )

        assert result.status == "blocked"
        assert result.executable is False
        assert (
            result.reason
            == "public_release_not_available_by_voice"
        )

    print(
        "PASS: public-release language is blocked."
    )


    result = router.parse(
        "list my goals"
    )

    assert result.status == "ready"
    assert result.agent == "goal"
    assert result.task == "list_goals"
    assert result.requires_confirmation is False

    print(
        "PASS: goal listing is read-only."
    )


    result = router.parse(
        "goal status"
    )

    assert result.status == "ready"
    assert result.task == "get_goal_status"
    assert result.requires_confirmation is False

    print(
        "PASS: goal status is read-only."
    )


    for command, expected_task in (
        (
            "create a goal",
            "create_goal",
        ),
        (
            "update my goal",
            "update_goal",
        ),
        (
            "pause my goal",
            "pause_goal",
        ),
        (
            "resume my goal",
            "resume_goal",
        ),
    ):
        result = router.parse(
            command
        )

        assert result.status == "ready"
        assert result.agent == "goal"
        assert result.task == expected_task
        assert result.requires_confirmation is True

    print(
        "PASS: goal mutations require confirmation."
    )


    result = router.parse(
        "create a video and upload the video"
    )

    assert result.status == "ambiguous"
    assert result.executable is False

    print(
        "PASS: multiple operations fail closed as ambiguous."
    )


    for command in (
        "",
        None,
        "tell me a joke",
        "delete everything",
        "run arbitrary python",
        "turn off the security system",
    ):
        result = router.parse(
            command
        )

        assert result.executable is False

    print(
        "PASS: unsupported commands have no execution target."
    )


    result = router.parse(
        "publish the video and analyze today's trends"
    )

    assert result.status == "blocked"
    assert result.executable is False

    print(
        "PASS: publication language takes precedence "
        "over otherwise safe commands."
    )


    assert (
        ("youtube", "publish_video")
        not in router._ALLOWED_TARGETS
    )

    print(
        "PASS: publish_video does not exist in "
        "the voice allowlist."
    )


    print()
    print(
        "PASS: VoiceCommandRouter regression "
        "suite complete."
    )


if __name__ == "__main__":
    main()
