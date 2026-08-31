"""Regression tests for Jarvis wake-phrase parsing."""

from backend.services.voice.wake_phrase import (
    WakePhraseParser,
)


def main():
    parser = WakePhraseParser()

    result = parser.parse(
        "Hey Jarvis, analyze today's trends"
    )

    assert result.detected is True
    assert (
        result.command
        == "analyze today's trends"
    )

    print(
        "PASS: standard wake phrase extracts command."
    )


    result = parser.parse(
        "hey jarvis create a video"
    )

    assert result.detected is True
    assert result.command == "create a video"

    print(
        "PASS: wake phrase matching is case-insensitive."
    )


    result = parser.parse(
        "HEY, JARVIS! Upload the finished video"
    )

    assert result.detected is True

    assert (
        result.command
        == "Upload the finished video"
    )

    print(
        "PASS: punctuation between wake words is tolerated."
    )


    result = parser.parse(
        "Hey Jarvis"
    )

    assert result.detected is True
    assert result.command == ""
    assert parser.is_wake_only(
        "Hey Jarvis"
    )

    print(
        "PASS: wake-only utterance is represented explicitly."
    )


    result = parser.parse(
        "Jarvis analyze trends"
    )

    assert result.detected is False
    assert result.command == ""

    print(
        "PASS: incomplete wake phrase is rejected."
    )


    result = parser.parse(
        "I was telling someone hey Jarvis yesterday"
    )

    assert result.detected is False

    print(
        "PASS: wake phrase inside ordinary speech is rejected."
    )


    result = parser.parse("")

    assert result.detected is False
    assert result.command == ""
    assert result.transcript == ""

    print(
        "PASS: empty recognition result is safe."
    )


    custom = WakePhraseParser(
        "okay jarvis"
    )

    result = custom.parse(
        "Okay Jarvis, status report"
    )

    assert result.detected is True
    assert result.command == "status report"

    print(
        "PASS: wake phrase is configurable."
    )


    try:
        WakePhraseParser("   ")
    except ValueError:
        pass
    else:
        raise AssertionError(
            "Empty wake phrase must be rejected."
        )

    print(
        "PASS: empty wake phrase configuration fails closed."
    )


    # Publication wording must remain ordinary command text
    # here. The voice layer itself receives no authority to
    # bypass downstream security boundaries.
    result = parser.parse(
        "Hey Jarvis publish the video publicly"
    )

    assert result.detected is True

    assert (
        result.command
        == "publish the video publicly"
    )

    print(
        "PASS: parser performs no privileged command execution."
    )


    print()
    print(
        "PASS: wake phrase regression suite complete."
    )


if __name__ == "__main__":
    main()
