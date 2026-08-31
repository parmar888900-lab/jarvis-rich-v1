
"""Regression tests for voice confirmation state."""

from backend.services.voice.command_router import (
    VoiceCommand,
)

from backend.services.voice.confirmation import (
    VoiceConfirmationManager,
)


class FakeClock:
    def __init__(self):
        self.value = 100.0

    def __call__(self):
        return self.value

    def advance(
        self,
        seconds,
    ):
        self.value += seconds


def upload_command():
    return VoiceCommand(
        status="ready",
        transcript="upload the video",
        agent="youtube",
        task="upload_video",
        parameters={
            "privacy_status": "private",
            "artifact": "test.mp4",
        },
        requires_confirmation=True,
    )


def test_exact_command_is_preserved():
    clock = FakeClock()

    manager = VoiceConfirmationManager(
        timeout_seconds=15,
        clock=clock,
    )

    command = upload_command()

    requested = manager.request(
        command
    )

    assert requested.status == "pending"
    assert requested.command is command
    assert manager.has_pending

    decision = manager.resolve(
        "Confirm."
    )

    assert decision.status == "confirmed"

    # The exact immutable parsed command is returned.
    assert decision.command is command

    assert (
        decision.command.parameters
        == {
            "privacy_status": "private",
            "artifact": "test.mp4",
        }
    )

    assert not manager.has_pending


def test_confirmation_is_single_use():
    manager = VoiceConfirmationManager()

    manager.request(
        upload_command()
    )

    first = manager.resolve(
        "yes confirm"
    )

    second = manager.resolve(
        "confirm"
    )

    assert first.status == "confirmed"
    assert second.status == "no_pending"


def test_cancel_consumes_pending_command():
    manager = VoiceConfirmationManager()

    manager.request(
        upload_command()
    )

    decision = manager.resolve(
        "No"
    )

    assert decision.status == "cancelled"
    assert decision.command is None
    assert not manager.has_pending

    replay = manager.resolve(
        "confirm"
    )

    assert replay.status == "no_pending"


def test_unknown_speech_fails_closed():
    manager = VoiceConfirmationManager()

    manager.request(
        upload_command()
    )

    decision = manager.resolve(
        "maybe later"
    )

    assert decision.status == "rejected"
    assert decision.command is None
    assert not manager.has_pending


def test_publication_language_blocks_and_consumes():
    manager = VoiceConfirmationManager()

    manager.request(
        upload_command()
    )

    decision = manager.resolve(
        "confirm and make it public"
    )

    assert decision.status == "blocked"

    assert (
        decision.reason
        == "public_release_not_available_by_voice"
    )

    assert decision.command is None
    assert not manager.has_pending


def test_publication_language_cannot_be_replayed():
    manager = VoiceConfirmationManager()

    manager.request(
        upload_command()
    )

    manager.resolve(
        "make it public"
    )

    replay = manager.resolve(
        "confirm"
    )

    assert replay.status == "no_pending"


def test_expiration_fails_closed():
    clock = FakeClock()

    manager = VoiceConfirmationManager(
        timeout_seconds=15,
        clock=clock,
    )

    manager.request(
        upload_command()
    )

    clock.advance(
        15
    )

    decision = manager.resolve(
        "confirm"
    )

    assert decision.status == "expired"
    assert decision.command is None
    assert not manager.has_pending


def test_has_pending_expires_stale_state():
    clock = FakeClock()

    manager = VoiceConfirmationManager(
        timeout_seconds=5,
        clock=clock,
    )

    manager.request(
        upload_command()
    )

    assert manager.has_pending

    clock.advance(
        5
    )

    assert not manager.has_pending


def test_non_confirmation_command_cannot_be_stored():
    manager = VoiceConfirmationManager()

    command = VoiceCommand(
        status="ready",
        transcript="analyze today's trends",
        agent="youtube",
        task="analyze_trends",
        requires_confirmation=False,
    )

    decision = manager.request(
        command
    )

    assert decision.status == "blocked"

    assert (
        decision.reason
        == "confirmation_not_required"
    )

    assert not manager.has_pending


def test_non_ready_command_cannot_be_stored():
    manager = VoiceConfirmationManager()

    command = VoiceCommand(
        status="blocked",
        transcript="make it public",
        reason=(
            "public_release_not_available_by_voice"
        ),
    )

    decision = manager.request(
        command
    )

    assert decision.status == "blocked"
    assert not manager.has_pending


def test_forged_publish_command_cannot_be_stored():
    manager = VoiceConfirmationManager()

    forged = VoiceCommand(
        status="ready",
        transcript="publish video",
        agent="youtube",
        task="publish_video",
        parameters={},
        requires_confirmation=True,
    )

    decision = manager.request(
        forged
    )

    assert decision.status == "blocked"

    assert (
        decision.reason
        == "forbidden_voice_target"
    )

    assert not manager.has_pending


def test_invalid_object_clears_existing_pending():
    manager = VoiceConfirmationManager()

    manager.request(
        upload_command()
    )

    assert manager.has_pending

    decision = manager.request(
        object()
    )

    assert decision.status == "blocked"
    assert not manager.has_pending


def test_replacement_is_explicit_and_single_slot():
    manager = VoiceConfirmationManager()

    first = upload_command()

    second = VoiceCommand(
        status="ready",
        transcript="pause goal",
        agent="goal",
        task="pause_goal",
        parameters={
            "goal_id": "goal-2",
        },
        requires_confirmation=True,
    )

    manager.request(
        first
    )

    manager.request(
        second
    )

    decision = manager.resolve(
        "confirm"
    )

    assert decision.status == "confirmed"
    assert decision.command is second

    assert (
        decision.command.task
        == "pause_goal"
    )


def test_configuration_fails_closed():
    try:
        VoiceConfirmationManager(
            timeout_seconds=0
        )
    except ValueError:
        pass
    else:
        raise AssertionError(
            "Zero timeout must fail."
        )

    try:
        VoiceConfirmationManager(
            timeout_seconds=True
        )
    except ValueError:
        pass
    else:
        raise AssertionError(
            "Boolean timeout must fail."
        )


def main():
    test_exact_command_is_preserved()
    print(
        "PASS: exact pending command is preserved."
    )

    test_confirmation_is_single_use()
    print(
        "PASS: confirmation is single-use."
    )

    test_cancel_consumes_pending_command()
    print(
        "PASS: cancellation consumes pending state."
    )

    test_unknown_speech_fails_closed()
    print(
        "PASS: unknown confirmation speech fails closed."
    )

    test_publication_language_blocks_and_consumes()
    print(
        "PASS: publication language blocks confirmation."
    )

    test_publication_language_cannot_be_replayed()
    print(
        "PASS: blocked publication cannot be replayed."
    )

    test_expiration_fails_closed()
    print(
        "PASS: expired confirmation cannot execute."
    )

    test_has_pending_expires_stale_state()
    print(
        "PASS: stale pending state expires automatically."
    )

    test_non_confirmation_command_cannot_be_stored()
    print(
        "PASS: safe commands cannot become pending confirmation."
    )

    test_non_ready_command_cannot_be_stored()
    print(
        "PASS: blocked commands cannot become pending."
    )

    test_forged_publish_command_cannot_be_stored()
    print(
        "PASS: forged publication cannot become pending."
    )

    test_invalid_object_clears_existing_pending()
    print(
        "PASS: malformed replacement clears pending state."
    )

    test_replacement_is_explicit_and_single_slot()
    print(
        "PASS: confirmation state contains one command only."
    )

    test_configuration_fails_closed()
    print(
        "PASS: invalid confirmation configuration fails closed."
    )

    print()
    print(
        "PASS: VoiceConfirmationManager "
        "regression suite complete."
    )


if __name__ == "__main__":
    main()
